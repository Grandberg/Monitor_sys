"""Persist last selected server and UI message IDs per Telegram chat."""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

from src.config import SESSION_STORE_PATH

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load() -> dict[str, Any]:
    path = SESSION_STORE_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to read session store {path}: {e}")
        return {}


def _save(data: dict[str, Any]) -> None:
    path = SESSION_STORE_PATH
    try:
        _ensure_parent(path)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        logger.error(f"Failed to write session store {path}: {e}")


def _entry(data: dict[str, Any], chat_id: int) -> dict[str, Any]:
    key = str(chat_id)
    entry = data.get(key)
    if not isinstance(entry, dict):
        entry = {}
        data[key] = entry
    return entry


def get_chat_session(chat_id: int) -> dict[str, Any]:
    with _lock:
        data = _load()
        entry = data.get(str(chat_id), {})
        return dict(entry) if isinstance(entry, dict) else {}


def set_last_server(chat_id: int, server_id: str, view: str = "panel") -> None:
    with _lock:
        data = _load()
        entry = _entry(data, chat_id)
        entry["last_server_id"] = server_id
        entry["last_view"] = view
        _save(data)


def get_last_server_id(chat_id: int) -> Optional[str]:
    session = get_chat_session(chat_id)
    value = session.get("last_server_id")
    return value if isinstance(value, str) and value else None


def get_ui_message_ids(chat_id: int) -> list[int]:
    session = get_chat_session(chat_id)
    raw = session.get("ui_message_ids", [])
    if not isinstance(raw, list):
        return []
    ids: list[int] = []
    for item in raw:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def set_ui_message_ids(chat_id: int, message_ids: list[int]) -> None:
    # Keep a bounded recent list (Telegram may refuse very old deletes anyway)
    cleaned = []
    seen = set()
    for mid in message_ids:
        try:
            value = int(mid)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    cleaned = cleaned[-50:]

    with _lock:
        data = _load()
        entry = _entry(data, chat_id)
        entry["ui_message_ids"] = cleaned
        _save(data)


def add_ui_message_id(chat_id: int, message_id: int) -> None:
    ids = get_ui_message_ids(chat_id)
    ids.append(int(message_id))
    set_ui_message_ids(chat_id, ids)


def clear_ui_message_ids(chat_id: int) -> None:
    set_ui_message_ids(chat_id, [])


def clear_last_server(chat_id: int) -> None:
    with _lock:
        data = _load()
        data.pop(str(chat_id), None)
        _save(data)
