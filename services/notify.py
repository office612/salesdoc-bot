"""Безопасная отправка сообщений: FloodWait, ForbiddenError, лог в Sheets."""

import asyncio
import logging
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import (
    TelegramRetryAfter,
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramNetworkError,
)
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup

from services.sheets import log_bot_error, get_user_name

logger = logging.getLogger(__name__)

# Telegram лимит: ~30 msg/sec в разные чаты. Берём с запасом — 50мс между отправками.
SEND_DELAY = 0.05
MAX_RETRIES = 2


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Tuple[bool, Optional[int]]:
    """Безопасная отправка текста. Возвращает (ok, message_id)."""
    return await _safe_send(bot, chat_id, text=text, reply_markup=reply_markup)


async def safe_send_photo(
    bot: Bot,
    chat_id: int,
    photo_bytes: bytes,
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Tuple[bool, Optional[int]]:
    """Безопасная отправка фото с подписью."""
    return await _safe_send(
        bot, chat_id, photo_bytes=photo_bytes, caption=caption, reply_markup=reply_markup
    )


async def _safe_send(
    bot: Bot,
    chat_id: int,
    text: Optional[str] = None,
    photo_bytes: Optional[bytes] = None,
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Tuple[bool, Optional[int]]:
    attempt = 0
    while attempt <= MAX_RETRIES:
        try:
            if photo_bytes:
                sent = await bot.send_photo(
                    chat_id,
                    BufferedInputFile(photo_bytes, filename="receipt.jpg"),
                    caption=caption,
                    reply_markup=reply_markup,
                )
            else:
                sent = await bot.send_message(
                    chat_id, text, reply_markup=reply_markup
                )
            return True, sent.message_id

        except TelegramRetryAfter as e:
            # Telegram просит подождать N секунд — ждём и повторяем
            wait = int(getattr(e, "retry_after", 5)) + 1
            logger.warning(f"FloodWait {wait}s для chat {chat_id}, ждём")
            await asyncio.sleep(wait)
            attempt += 1
            continue

        except TelegramForbiddenError:
            # Юзер заблокировал бота или удалил чат
            _log_safe(chat_id, "blocked_by_user", "Юзер заблокировал бота")
            return False, None

        except TelegramBadRequest as e:
            # chat not found / message too long / прочие плохие запросы
            _log_safe(chat_id, "bad_request", str(e)[:200])
            return False, None

        except TelegramNetworkError as e:
            # Временная сетевая проблема — короткая пауза и повтор
            logger.warning(f"Network error для chat {chat_id}: {e}")
            await asyncio.sleep(2)
            attempt += 1
            continue

        except Exception as e:
            _log_safe(chat_id, "unknown", f"{type(e).__name__}: {str(e)[:200]}")
            return False, None

    _log_safe(chat_id, "retry_exhausted", "Превышено число повторов")
    return False, None


def _log_safe(chat_id: int, error_type: str, details: str):
    """Лог в Sheets с fallback на logger — чтоб никакая ошибка лога не сломала отправку."""
    try:
        name = get_user_name(chat_id) or "—"
        log_bot_error(chat_id, name, error_type, details)
    except Exception as e:
        logger.error(f"log_bot_error failed for {chat_id}: {e}")
