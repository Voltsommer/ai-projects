"""本地演示数据库的受控人工增删与恢复。"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from numbers import Integral
from pathlib import Path
from typing import Iterable

import pandas as pd

from database import DatabaseAccessError, connect_read_only, require_known_table
from init_db import REQUIRED_COLUMNS, SampleDatabaseError, load_sample_dataframe


MAX_MANAGED_ROWS = 1_000
MAX_DELETE_ROWS = 100
MAX_TEXT_LENGTH = 100
MAX_QUANTITY = 1_000_000_000
MAX_REVENUE = 1_000_000_000_000


class DataManagementError(RuntimeError):
    """人工数据管理请求无效或数据库写入失败。"""


def list_sales_records(
    database_file: str | Path,
    *,
    limit: int = MAX_MANAGED_ROWS,
) -> pd.DataFrame:
    """读取可供人工管理的销售记录，并暴露 SQLite 行标识。"""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_MANAGED_ROWS:
        raise ValueError(f"管理列表行数必须在 1 到 {MAX_MANAGED_ROWS} 之间。")

    try:
        with closing(connect_read_only(database_file)) as connection:
            require_known_table(connection, "sales")
            return pd.read_sql_query(
                """
                SELECT rowid AS 记录ID, 商品, 品类, 月份, 地区, 销量, 销售额
                FROM sales
                ORDER BY rowid
                LIMIT ?
                """,
                connection,
                params=(limit,),
            )
    except (DatabaseAccessError, sqlite3.Error, pd.errors.DatabaseError) as exc:
        raise DataManagementError("无法读取演示数据管理列表。") from exc


def add_sales_record(
    database_file: str | Path,
    *,
    product: str,
    category: str,
    month: str,
    region: str,
    quantity: int,
    revenue: int,
) -> int:
    """通过参数化 SQL 新增一条经过服务端校验的销售记录。"""
    values = (
        _normalise_text("商品", product),
        _normalise_text("品类", category),
        _normalise_text("月份", month),
        _normalise_text("地区", region),
        _normalise_integer("销量", quantity, maximum=MAX_QUANTITY),
        _normalise_integer("销售额", revenue, maximum=MAX_REVENUE),
    )

    with closing(_connect_for_management(database_file)) as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO sales (商品, 品类, 月份, 地区, 销量, 销售额)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            connection.commit()
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            connection.rollback()
            raise DataManagementError("新增记录失败，数据库未发生变化。") from exc


def delete_sales_records(
    database_file: str | Path,
    record_ids: Iterable[int],
) -> int:
    """原子删除所选记录；任一编号不存在时不删除任何记录。"""
    identifiers = _normalise_record_ids(record_ids)
    placeholders = ", ".join("?" for _ in identifiers)

    with closing(_connect_for_management(database_file)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_count = connection.execute(
                f"SELECT COUNT(*) FROM sales WHERE rowid IN ({placeholders})",
                identifiers,
            ).fetchone()[0]
            if existing_count != len(identifiers):
                raise DataManagementError("所选记录已发生变化，请刷新后重新选择。")

            cursor = connection.execute(
                f"DELETE FROM sales WHERE rowid IN ({placeholders})",
                identifiers,
            )
            connection.commit()
            return int(cursor.rowcount)
        except DataManagementError:
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise DataManagementError("删除记录失败，数据库未发生变化。") from exc


def restore_sample_records(
    database_file: str | Path,
    sample_csv_file: str | Path,
) -> int:
    """在单个事务中把 sales 表恢复为仓库内的示例数据。"""
    try:
        dataframe = load_sample_dataframe(sample_csv_file)
    except SampleDatabaseError as exc:
        raise DataManagementError(str(exc)) from exc

    rows = list(dataframe[REQUIRED_COLUMNS].itertuples(index=False, name=None))
    with closing(_connect_for_management(database_file)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM sales")
            connection.executemany(
                """
                INSERT INTO sales (商品, 品类, 月份, 地区, 销量, 销售额)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()
            return len(rows)
        except sqlite3.Error as exc:
            connection.rollback()
            raise DataManagementError("恢复示例数据失败，数据库未发生变化。") from exc


def _connect_for_management(database_file: str | Path) -> sqlite3.Connection:
    path = Path(database_file).resolve()
    if not path.is_file():
        raise DataManagementError(f"找不到数据库文件：{path.name}")

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path, timeout=5)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        columns = {
            str(row[1])
            for row in connection.execute('PRAGMA table_info("sales")').fetchall()
        }
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
        if missing_columns:
            raise DataManagementError("演示数据表结构不完整，无法执行数据管理操作。")
        return connection
    except DataManagementError:
        if connection is not None:
            connection.close()
        raise
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        raise DataManagementError("数据库无法进入人工管理模式。") from exc


def _normalise_text(label: str, value: str) -> str:
    if not isinstance(value, str):
        raise DataManagementError(f"{label}必须是文本。")
    normalised = value.strip()
    if not normalised:
        raise DataManagementError(f"{label}不能为空。")
    if len(normalised) > MAX_TEXT_LENGTH:
        raise DataManagementError(f"{label}不能超过 {MAX_TEXT_LENGTH} 个字符。")
    return normalised


def _normalise_integer(label: str, value: int, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise DataManagementError(f"{label}必须是整数。")
    normalised = int(value)
    if not 0 <= normalised <= maximum:
        raise DataManagementError(f"{label}必须在 0 到 {maximum:,} 之间。")
    return normalised


def _normalise_record_ids(record_ids: Iterable[int]) -> tuple[int, ...]:
    if isinstance(record_ids, (str, bytes)):
        raise DataManagementError("请选择有效的记录。")
    try:
        raw_identifiers = list(record_ids)
    except TypeError as exc:
        raise DataManagementError("请选择有效的记录。") from exc

    if not raw_identifiers:
        raise DataManagementError("请至少选择一条要删除的记录。")
    if len(raw_identifiers) > MAX_DELETE_ROWS:
        raise DataManagementError(f"一次最多删除 {MAX_DELETE_ROWS} 条记录。")
    if any(
        isinstance(identifier, bool)
        or not isinstance(identifier, Integral)
        or int(identifier) < 1
        for identifier in raw_identifiers
    ):
        raise DataManagementError("记录编号必须是正整数。")

    identifiers = tuple(sorted({int(identifier) for identifier in raw_identifiers}))
    if len(identifiers) != len(raw_identifiers):
        raise DataManagementError("所选记录中包含重复编号。")
    return identifiers
