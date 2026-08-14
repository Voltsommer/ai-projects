"""SQLite 数据源的只读连接、元数据与安全预览。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


class DatabaseAccessError(RuntimeError):
    """数据库不存在、不可读或元数据无效。"""


def connect_read_only(database_file: str | Path) -> sqlite3.Connection:
    path = Path(database_file).resolve()
    if not path.is_file():
        raise DatabaseAccessError(f"找不到数据库文件：{path.name}")

    uri_path = path.as_posix()
    try:
        connection = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
    except sqlite3.Error as exc:
        raise DatabaseAccessError("数据库无法以只读方式打开。") from exc
    return connection


def list_user_tables(connection: sqlite3.Connection) -> list[str]:
    try:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise DatabaseAccessError("无法读取数据库表清单。") from exc
    return [str(row[0]) for row in rows]


def get_schema_text(connection: sqlite3.Connection, table: str) -> str:
    table_name = require_known_table(connection, table)
    try:
        rows = connection.execute(
            f"PRAGMA table_info({_quote_identifier(table_name)})"
        ).fetchall()
    except sqlite3.Error as exc:
        raise DatabaseAccessError("无法读取数据表结构。") from exc

    if not rows:
        raise DatabaseAccessError("所选数据表没有可读取的字段。")
    columns = ", ".join(f"{row[1]} {row[2] or 'TEXT'}" for row in rows)
    return f"表 {table_name} 的列：{columns}"


def preview_table(
    connection: sqlite3.Connection,
    table: str,
    *,
    limit: int = 5,
) -> pd.DataFrame:
    if limit < 1 or limit > 100:
        raise ValueError("预览行数必须在 1 到 100 之间。")
    table_name = require_known_table(connection, table)
    try:
        return pd.read_sql_query(
            f"SELECT * FROM {_quote_identifier(table_name)} LIMIT ?",
            connection,
            params=(limit,),
        )
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        raise DatabaseAccessError("无法读取数据表预览。") from exc


def require_known_table(connection: sqlite3.Connection, table: str) -> str:
    if not isinstance(table, str) or not table:
        raise DatabaseAccessError("请选择有效的数据表。")
    if table not in list_user_tables(connection):
        raise DatabaseAccessError("所选数据表不在允许访问的清单中。")
    return table


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
