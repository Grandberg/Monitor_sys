"""Persist last selected server (and optional view) per Telegram chat."""
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


def get_chat_session(chat_id: int) -> dict[str, Any]:
    with _lock:
        data = _load()
        entry = data.get(str(chat_id), {})
        return entry if isinstance(entry, dict) else {}


def set_last_server(chat_id: int, server_id: str, view: str = "panel") -> None:
    with _lock:
        data = _load()
        data[str(chat_id)] = {
            "last_server_id": server_id,
            "last_view": view,
        }
        _save(data)


def get_last_server_id(chat_id: int) -> Optional[str]:
    session = get_chat_session(chat_id)
    value = session.get("last_server_id")
    return value if isinstance(value, str) and value else None


def clear_last_server(chat_id: int) -> None:
    with _lock:
        data = _load()
        data.pop(str(chat_id), None)
        _save(data)
