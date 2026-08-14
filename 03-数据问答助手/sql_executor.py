"""SQLite 查询的清洗、校验和受限执行。

这个模块不依赖 Streamlit 或大模型 API，因此可以独立测试。
"""

import re
import sqlite3
import time

import pandas as pd


DEFAULT_MAX_ROWS = 200
DEFAULT_TIMEOUT_SECONDS = 3.0


class SqlValidationError(ValueError):
    """AI 生成的内容不是允许执行的单条只读查询。"""


class SqlExecutionError(RuntimeError):
    """查询通过校验，但在受限执行阶段失败。"""


def clean_sql_output(raw_sql: str) -> str:
    """去掉模型偶尔返回的 Markdown 代码块和 ``SQL:`` 前缀。"""
    if not isinstance(raw_sql, str) or not raw_sql.strip():
        raise SqlValidationError("AI 没有返回可执行的 SQL。")

    sql = raw_sql.strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", sql, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        sql = fenced.group(1).strip()

    sql = re.sub(r"^sql\s*:\s*", "", sql, count=1, flags=re.IGNORECASE).strip()
    if not sql:
        raise SqlValidationError("清洗后没有可执行的 SQL。")
    return sql


def _skip_leading_comments(sql: str) -> str:
    """移除开头的 SQL 注释，便于判断查询的第一个关键字。"""
    remaining = sql.lstrip()
    while True:
        if remaining.startswith("--"):
            newline = remaining.find("\n")
            remaining = "" if newline == -1 else remaining[newline + 1 :].lstrip()
        elif remaining.startswith("/*"):
            end = remaining.find("*/", 2)
            if end == -1:
                raise SqlValidationError("SQL 注释没有正确结束。")
            remaining = remaining[end + 2 :].lstrip()
        else:
            return remaining


def _has_multiple_statements(sql: str) -> bool:
    """识别字符串和注释之外的分号，拒绝一次执行多条语句。"""
    statement_ended = False
    index = 0
    state = "normal"

    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""

        if state == "normal":
            if statement_ended and not char.isspace():
                return True
            if char == "'":
                state = "single_quote"
            elif char == '"':
                state = "double_quote"
            elif char == "-" and next_char == "-":
                state = "line_comment"
                index += 1
            elif char == "/" and next_char == "*":
                state = "block_comment"
                index += 1
            elif char == ";":
                statement_ended = True
        elif state == "single_quote":
            if char == "'":
                if next_char == "'":
                    index += 1
                else:
                    state = "normal"
        elif state == "double_quote":
            if char == '"':
                if next_char == '"':
                    index += 1
                else:
                    state = "normal"
        elif state == "line_comment":
            if char == "\n":
                state = "normal"
        elif state == "block_comment" and char == "*" and next_char == "/":
            state = "normal"
            index += 1

        index += 1

    if state in {"single_quote", "double_quote", "block_comment"}:
        raise SqlValidationError("SQL 中存在没有正确结束的引号或注释。")
    return False


def validate_read_only_query(raw_sql: str) -> str:
    """返回清洗后的 SQL；只允许单条 ``SELECT`` 或 ``WITH`` 查询。"""
    sql = clean_sql_output(raw_sql)
    query_start = _skip_leading_comments(sql)
    first_keyword = re.match(r"[A-Za-z]+", query_start)

    if not first_keyword or first_keyword.group(0).upper() not in {"SELECT", "WITH"}:
        raise SqlValidationError("只允许执行 SELECT 或 WITH 开头的只读查询。")
    if _has_multiple_statements(sql):
        raise SqlValidationError("一次只允许执行一条 SQL 查询。")
    return sql


def _build_read_only_authorizer(allowed_tables=None):
    """SQLite 的第二层防护：即使文本校验漏掉，也拒绝修改数据库。"""
    denied_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_ANALYZE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_SAVEPOINT,
    }
    allowed_table_names = set(allowed_tables) if allowed_tables is not None else None

    def authorizer(action_code, parameter_1, parameter_2, database_name, trigger_name):
        del database_name, trigger_name
        if action_code in denied_actions:
            return sqlite3.SQLITE_DENY
        if (
            action_code == sqlite3.SQLITE_READ
            and allowed_table_names is not None
            and parameter_1 not in allowed_table_names
        ):
            return sqlite3.SQLITE_DENY

        function_name = parameter_2 or parameter_1
        if action_code == sqlite3.SQLITE_FUNCTION and str(function_name).lower() == "load_extension":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return authorizer


def execute_read_only_query(
    raw_sql: str,
    conn: sqlite3.Connection,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    allowed_tables=None,
) -> pd.DataFrame:
    """在只读授权、超时和结果行数限制下执行查询。"""
    if max_rows < 1:
        raise ValueError("max_rows 必须大于 0。")
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds 不能小于 0。")

    sql = validate_read_only_query(raw_sql)
    started_at = time.monotonic()

    def query_timed_out():
        return int(time.monotonic() - started_at >= timeout_seconds)

    conn.set_authorizer(_build_read_only_authorizer(allowed_tables))
    conn.set_progress_handler(query_timed_out, 100)
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(max_rows + 1)
        columns = [description[0] for description in cursor.description or []]
    except sqlite3.DatabaseError as error:
        if "interrupted" in str(error).lower():
            raise SqlExecutionError(f"查询超过 {timeout_seconds:g} 秒，已自动终止。") from error
        raise SqlExecutionError(f"SQL 执行失败：{error}") from error
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_authorizer(None)

    result = pd.DataFrame.from_records(rows[:max_rows], columns=columns)
    result.attrs["truncated"] = len(rows) > max_rows
    result.attrs["max_rows"] = max_rows
    return result
