"""从仓库内的示例 CSV 创建可重复生成的 SQLite 演示数据库。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["商品", "品类", "月份", "地区", "销量", "销售额"]


class SampleDatabaseError(RuntimeError):
    """示例数据缺失、结构无效或数据库无法创建。"""


def load_sample_dataframe(csv_file) -> pd.DataFrame:
    """读取并校验仓库内的示例 CSV。"""
    csv_path = Path(csv_file).resolve()
    if not csv_path.is_file():
        raise SampleDatabaseError("找不到 sample_data.csv 示例数据。")

    try:
        dataframe = pd.read_csv(csv_path)
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise SampleDatabaseError("示例 CSV 无法读取。") from exc

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in dataframe.columns
    ]
    if missing_columns:
        raise SampleDatabaseError(
            "示例数据缺少字段：" + "、".join(missing_columns)
        )
    if dataframe.empty:
        raise SampleDatabaseError("示例数据没有可写入的记录。")
    return dataframe[REQUIRED_COLUMNS].copy()


def create_sample_database(csv_file, database_file) -> int:
    dataframe = load_sample_dataframe(csv_file)
    database_path = Path(database_file).resolve()

    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = database_path.with_name(f".{database_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute(
                """
                CREATE TABLE sales (
                    商品 TEXT NOT NULL,
                    品类 TEXT NOT NULL,
                    月份 TEXT NOT NULL,
                    地区 TEXT NOT NULL,
                    销量 INTEGER NOT NULL,
                    销售额 INTEGER NOT NULL
                )
                """
            )
            rows = dataframe.itertuples(index=False, name=None)
            connection.executemany(
                "INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            connection.commit()
        finally:
            connection.close()
        temporary_path.replace(database_path)
    except (OSError, sqlite3.Error) as exc:
        temporary_path.unlink(missing_ok=True)
        raise SampleDatabaseError("示例数据库创建失败。") from exc
    return len(dataframe)


def ensure_sample_database(base_dir) -> Path:
    root = Path(base_dir).resolve()
    database_path = root / "sales.db"
    if not database_path.exists():
        create_sample_database(root / "sample_data.csv", database_path)
    return database_path


if __name__ == "__main__":
    project_dir = Path(__file__).resolve().parent
    created_rows = create_sample_database(
        project_dir / "sample_data.csv",
        project_dir / "sales.db",
    )
    print(f"已创建 sales.db，表 sales，共 {created_rows} 行。")
