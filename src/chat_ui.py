"""Helpers to keep the Telegram chat clean: one UI message at a time."""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, Message

import src.session as session

logger = logging.getLogger(__name__)


async def _delete_one(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.debug(f"Could not delete message {message_id} in chat {chat_id}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error deleting message {message_id} in chat {chat_id}: {e}")


async def purge_chat_messages(
    bot: Bot,
    chat_id: int,
    *,
    extra_ids: Optional[Iterable[int]] = None,
    keep_ids: Optional[Iterable[int]] = None,
) -> None:
    """Delete tracked UI messages plus any extra IDs (e.g. user's /start)."""
    keep = {int(x) for x in (keep_ids or [])}
    to_delete = set(session.get_ui_message_ids(chat_id))
    if extra_ids:
        to_delete.update(int(x) for x in extra_ids)

    for message_id in sorted(to_delete):
        if message_id in keep:
            continue
        await _delete_one(bot, chat_id, message_id)

    # Drop deleted IDs from store; keep only explicitly preserved ones
    remaining = [mid for mid in session.get_ui_message_ids(chat_id) if mid in keep]
    session.set_ui_message_ids(chat_id, remaining)


async def send_clean_ui(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "Markdown",
    extra_delete_ids: Optional[Iterable[int]] = None,
) -> Message:
    """
    Delete all previous UI / startup / command messages, then send a fresh UI message.
    """
    await purge_chat_messages(bot, chat_id, extra_ids=extra_delete_ids)
    sent = await bot.send_message(
        chat_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
    session.set_ui_message_ids(chat_id, [sent.message_id])
    return sent


async def edit_or_replace_ui(
    bot: Bot,
    chat_id: int,
    message: Message,
    text: str,
    *,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "Markdown",
) -> Message:
    """
    Prefer editing the current callback message; if edit fails, send a clean replacement.
    Always keep only this one UI message tracked.
    """
    # Remove any other leftover UI messages (startup, old panels), keep current
    await purge_chat_messages(
        bot,
        chat_id,
        keep_ids=[message.message_id],
    )

    try:
        edited = await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        # edit_text may return True in some versions; normalize to Message
        if isinstance(edited, Message):
            session.set_ui_message_ids(chat_id, [edited.message_id])
            return edited
        session.set_ui_message_ids(chat_id, [message.message_id])
        return message
    except TelegramBadRequest as e:
        # e.g. "message is not modified" — treat as success for identical content
        if "message is not modified" in str(e).lower():
            session.set_ui_message_ids(chat_id, [message.message_id])
            return message
        logger.info(f"edit_text failed in chat {chat_id}, replacing: {e}")
    except Exception as e:
        logger.info(f"edit_text failed in chat {chat_id}, replacing: {e}")

    # Current message may already be gone — delete it too, then send fresh
    return await send_clean_ui(
        bot,
        chat_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        extra_delete_ids=[message.message_id],
    )


async def track_outbound_ui(chat_id: int, message: Message) -> Message:
    session.add_ui_message_id(chat_id, message.message_id)
    return message
