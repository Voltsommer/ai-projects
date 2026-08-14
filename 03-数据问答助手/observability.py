"""隐私友好的 JSON Lines 运行事件日志。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ALLOWED_STATUSES = {"success", "error"}
ALLOWED_SOURCES = {"database", "file"}


class EventLogError(RuntimeError):
    """运行事件无法写入日志。"""


def new_request_id() -> str:
    return uuid4().hex


def write_analysis_event(
    path: str | Path,
    *,
    request_id: str,
    status: str,
    source: str,
    duration_ms: int,
    result_rows: int | None = None,
    error_type: str | None = None,
) -> dict:
    """追加一次分析事件；不接受问题正文、SQL、数据内容或密钥。"""
    if status not in ALLOWED_STATUSES:
        raise ValueError("status 必须是 success 或 error。")
    if source not in ALLOWED_SOURCES:
        raise ValueError("source 必须是 database 或 file。")
    if duration_ms < 0:
        raise ValueError("duration_ms 不能小于 0。")
    if status == "success" and error_type is not None:
        raise ValueError("成功事件不能包含 error_type。")
    if status == "error" and not error_type:
        raise ValueError("失败事件必须包含 error_type。")

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "analysis_request",
        "request_id": str(request_id),
        "status": status,
        "source": source,
        "duration_ms": int(duration_ms),
        "result_rows": int(result_rows) if result_rows is not None else None,
        "error_type": str(error_type) if error_type else None,
    }

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
    except OSError as exc:
        raise EventLogError("运行事件日志写入失败。") from exc
    return event
