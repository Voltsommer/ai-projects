"""数据文件读取、接入限制与可解释的数据质量报告。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_DATA_ROWS = 100_000
MAX_DATA_COLUMNS = 100
SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
MISSING_RATE_WARNING = 0.2


class DataQualityError(ValueError):
    """上传文件或数据集不符合接入要求。"""


def validate_upload_metadata(
    file_name: str,
    file_size: int,
    *,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    """校验文件名、扩展名和体积，返回标准化扩展名。"""
    extension = Path(file_name or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DataQualityError("仅支持 CSV 或 Excel（.xlsx）文件。")
    if file_size <= 0:
        raise DataQualityError("文件内容为空，请重新选择有效的数据文件。")
    if file_size > max_bytes:
        limit_mb = max_bytes / 1024 / 1024
        raise DataQualityError(f"文件超过 {limit_mb:g} MB 的接入限制。")
    return extension


def load_tabular_data(
    file_bytes: bytes,
    extension: str,
    *,
    max_rows: int = MAX_DATA_ROWS,
) -> pd.DataFrame:
    """读取受支持的表格文件，并在进入分析前限制最大行数。"""
    if not file_bytes:
        raise DataQualityError("文件内容为空，请重新选择有效的数据文件。")

    try:
        if extension == ".csv":
            data = _read_csv(file_bytes, max_rows + 1)
        elif extension == ".xlsx":
            data = pd.read_excel(BytesIO(file_bytes), nrows=max_rows + 1)
        else:
            raise DataQualityError("仅支持 CSV 或 Excel（.xlsx）文件。")
    except DataQualityError:
        raise
    except Exception as exc:
        raise DataQualityError(
            "无法读取该文件，请确认文件未损坏且表头位于第一行。"
        ) from exc

    if len(data) > max_rows:
        raise DataQualityError(f"数据超过 {max_rows:,} 行的接入限制。")
    return data


def _read_csv(file_bytes: bytes, nrows: int) -> pd.DataFrame:
    """优先读取 UTF-8，兼容常见的中文 Windows CSV 编码。"""
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return pd.read_csv(BytesIO(file_bytes), encoding=encoding, nrows=nrows)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise DataQualityError("无法读取 CSV 文件。")


def analyse_data_quality(
    df: pd.DataFrame,
    *,
    max_rows: int = MAX_DATA_ROWS,
    max_columns: int = MAX_DATA_COLUMNS,
) -> dict:
    """生成包含阻断项、警告项和字段统计的可解释质量报告。"""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("数据质量分析只接受 pandas DataFrame。")

    row_count, column_count = df.shape
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum()) if column_count else 0
    duplicate_columns = _find_duplicate_columns(df)
    columns_with_series = [
        (str(column), df.iloc[:, position])
        for position, column in enumerate(df.columns)
    ]
    empty_columns = [
        column_name
        for column_name, series in columns_with_series
        if series.isna().all()
    ]
    unnamed_columns = [
        str(column)
        for column in df.columns
        if not str(column).strip() or str(column).lower().startswith("unnamed:")
    ]
    constant_columns = [
        column_name
        for column_name, series in columns_with_series
        if not series.isna().all() and series.nunique(dropna=True) <= 1
    ]

    blockers: list[str] = []
    warnings: list[str] = []

    if column_count == 0:
        blockers.append("未识别到任何字段。")
    if row_count == 0:
        blockers.append("文件只有表头，没有可分析的数据行。")
    if row_count > max_rows:
        blockers.append(f"数据超过 {max_rows:,} 行的接入限制。")
    if column_count > max_columns:
        blockers.append(f"字段数超过 {max_columns} 列的接入限制。")
    if duplicate_columns:
        blockers.append("存在重复字段名：" + "、".join(duplicate_columns))

    if missing_cells:
        warnings.append(f"存在 {missing_cells:,} 个缺失值，分析时需留意统计口径。")
    if duplicate_rows:
        warnings.append(f"存在 {duplicate_rows:,} 行完全重复的数据。")
    if empty_columns:
        warnings.append("存在全空字段：" + "、".join(empty_columns))
    if unnamed_columns:
        warnings.append("存在未命名字段：" + "、".join(unnamed_columns))
    if constant_columns:
        warnings.append("存在单一值字段：" + "、".join(constant_columns))
    if column_count == 1 and not blockers:
        warnings.append("当前只有 1 个字段，可支持的对比分析较有限。")

    profiles = [
        _build_column_profile(column_name, series)
        for column_name, series in columns_with_series
    ]
    high_missing_columns = [
        profile["字段"]
        for profile in profiles
        if profile["缺失率"] >= MISSING_RATE_WARNING
    ]
    if high_missing_columns:
        warnings.append(
            "以下字段缺失率不低于 20%：" + "、".join(high_missing_columns)
        )

    if blockers:
        status = "不可分析"
    elif warnings:
        status = "可分析，存在质量提醒"
    else:
        status = "质量检查通过"

    return {
        "status": status,
        "is_usable": not blockers,
        "row_count": int(row_count),
        "column_count": int(column_count),
        "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows,
        "blockers": blockers,
        "warnings": _deduplicate(warnings),
        "column_profiles": profiles,
    }


def _find_duplicate_columns(df: pd.DataFrame) -> list[str]:
    columns = pd.Index([str(column) for column in df.columns])
    return list(dict.fromkeys(columns[columns.duplicated()].tolist()))


def _build_column_profile(column_name: str, series: pd.Series) -> dict:
    missing_count = int(series.isna().sum())
    row_count = len(series)
    return {
        "字段": column_name,
        "数据类型": _friendly_dtype(series),
        "非空数": int(series.notna().sum()),
        "缺失数": missing_count,
        "缺失率": missing_count / row_count if row_count else 0.0,
        "唯一值数": int(series.nunique(dropna=True)),
    }


def _friendly_dtype(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "日期时间"
    if pd.api.types.is_bool_dtype(series):
        return "布尔"
    if pd.api.types.is_integer_dtype(series):
        return "整数"
    if pd.api.types.is_float_dtype(series):
        return "小数"
    if pd.api.types.is_numeric_dtype(series):
        return "数值"
    return "文本"


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
