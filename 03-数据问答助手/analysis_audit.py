"""构建可持久化的分析审计记录，不依赖 Streamlit。"""

import json

import pandas as pd


DEFAULT_PREVIEW_ROWS = 20
MAX_TEXT_LENGTH = 4000
PERSISTED_MESSAGE_FIELDS = ("role", "content", "analysis")


def _normalise_table(result) -> pd.DataFrame:
    if isinstance(result, pd.Series):
        return result.rename(result.name or "值").reset_index()

    table = result.copy()
    if not isinstance(table.index, pd.RangeIndex):
        try:
            table = table.reset_index()
        except ValueError:
            pass
    table.columns = [str(column) for column in table.columns]
    return table


def build_result_preview(result, max_rows=DEFAULT_PREVIEW_ROWS) -> dict:
    """把执行结果转换成体积受限、可写入 JSON 的预览。"""
    if isinstance(result, (pd.Series, pd.DataFrame)):
        table = _normalise_table(result)
        total_rows = len(table)
        preview = table.head(max_rows)
        payload = json.loads(
            preview.to_json(
                orient="split",
                force_ascii=False,
                date_format="iso",
                default_handler=str,
            )
        )
        return {
            "kind": "table",
            "columns": payload["columns"],
            "data": payload["data"],
            "total_rows": total_rows,
            "shown_rows": len(preview),
            "truncated": total_rows > len(preview),
        }

    text = str(result)
    truncated = len(text) > MAX_TEXT_LENGTH
    return {
        "kind": "text",
        "value": text[:MAX_TEXT_LENGTH],
        "truncated": truncated,
    }


def build_analysis_record(execution_type, code, language, result) -> dict:
    """记录一次分析所使用的逻辑与执行结果预览。"""
    return {
        "execution_type": execution_type,
        "code": code,
        "language": language,
        "result_preview": build_result_preview(result),
    }


def result_preview_to_dataframe(preview) -> pd.DataFrame | None:
    if not preview or preview.get("kind") != "table":
        return None
    return pd.DataFrame(preview.get("data", []), columns=preview.get("columns", []))


def serialise_messages(messages) -> list[dict]:
    """只持久化聊天展示与审计所需字段，排除 DataFrame 等运行时对象。"""
    return [
        {
            field: message[field]
            for field in PERSISTED_MESSAGE_FIELDS
            if field in message
        }
        for message in messages
    ]
