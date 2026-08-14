"""聊天审计记录的可靠本地持久化。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from analysis_audit import serialise_messages


class PersistenceError(RuntimeError):
    """聊天记录无法读取或保存。"""


def load_messages(path) -> tuple[list[dict], str | None]:
    """读取并校验聊天记录；损坏文件会被隔离并返回空会话。"""
    target = Path(path)
    if not target.exists():
        return [], None

    try:
        with target.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        messages = _validate_messages(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, PersistenceError) as exc:
        backup_path = _quarantine_corrupt_file(target)
        warning = "聊天记录无法恢复，已重新开始空会话。"
        if backup_path is not None:
            warning += f" 损坏文件已保留为 {backup_path.name}。"
        else:
            warning += f" 原文件隔离失败：{exc}"
        return [], warning

    return messages, None


def save_messages(path, messages) -> None:
    """先完整写入临时文件，再原子替换正式文件。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    clean_messages = serialise_messages(messages)
    _validate_messages(clean_messages)

    temporary = target.with_name(f".{target.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(clean_messages, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PersistenceError("聊天记录保存失败，请检查目录写入权限。") from exc


def _validate_messages(payload) -> list[dict]:
    if not isinstance(payload, list):
        raise PersistenceError("聊天记录顶层结构必须是列表。")

    validated: list[dict] = []
    for index, message in enumerate(payload):
        if not isinstance(message, dict):
            raise PersistenceError(f"第 {index + 1} 条聊天记录格式无效。")
        if message.get("role") not in {"user", "assistant"}:
            raise PersistenceError(f"第 {index + 1} 条聊天记录角色无效。")
        if not isinstance(message.get("content"), str):
            raise PersistenceError(f"第 {index + 1} 条聊天内容无效。")
        analysis = message.get("analysis")
        if analysis is not None and not isinstance(analysis, dict):
            raise PersistenceError(f"第 {index + 1} 条分析记录无效。")
        validated.append(message)
    return validated


def _quarantine_corrupt_file(target: Path) -> Path | None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = target.with_name(f"{target.stem}.corrupt-{timestamp}{target.suffix}")
    try:
        os.replace(target, backup_path)
    except OSError:
        return None
    return backup_path
