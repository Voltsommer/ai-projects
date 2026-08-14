"""集中管理运行配置，避免路径和环境变量散落在 UI 中。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_MODEL = "deepseek-chat"


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    api_key: str | None
    model: str
    environment: str
    chat_file: Path
    data_file: Path
    database_file: Path
    event_log_file: Path

    @property
    def ai_enabled(self) -> bool:
        return bool(self.api_key)


def load_config(
    base_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """从环境变量加载配置，并为所有运行时文件生成绝对路径。"""
    env = os.environ if environ is None else environ
    root = Path(base_dir or Path(__file__).resolve().parent).resolve()
    api_key = _normalise_optional(env.get("DEEPSEEK_API_KEY"))
    model = _normalise_optional(env.get("DEEPSEEK_MODEL")) or DEFAULT_MODEL
    environment = _normalise_optional(env.get("APP_ENV")) or "development"

    if environment not in {"development", "test", "production"}:
        raise ValueError("APP_ENV 只允许 development、test 或 production。")

    return AppConfig(
        base_dir=root,
        api_key=api_key,
        model=model,
        environment=environment,
        chat_file=root / "chat_history.json",
        data_file=root / "data.csv",
        database_file=root / "sales.db",
        event_log_file=root / "analysis_events.jsonl",
    )


def _normalise_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
