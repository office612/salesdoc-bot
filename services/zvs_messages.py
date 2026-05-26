"""Хранилище (zvs_id → chat_id, message_id) сообщений-подтверждений
у заявителя. Используется чтобы при одобрении РЕДАКТИРОВАТЬ исходное
сообщение, а не слать новое.

Двухуровневый кэш: память (быстро) + Sheets (переживает рестарты бота)."""

import logging
from services.zvs_sheets import save_applicant_message, get_applicant_message

logger = logging.getLogger(__name__)

_cache: dict = {}  # {zvs_id: (chat_id, message_id)} — быстрый кэш


def save(zvs_id: int, chat_id: int, message_id: int):
    _cache[int(zvs_id)] = (int(chat_id), int(message_id))
    # Дублируем в Sheets, чтоб после рестарта бот помнил
    try:
        save_applicant_message(zvs_id, chat_id, message_id)
    except Exception as e:
        logger.error(f"save to sheets failed: {e}")


def get(zvs_id: int):
    cached = _cache.get(int(zvs_id))
    if cached:
        return cached
    # Fallback: читаем из Sheets
    try:
        loc = get_applicant_message(zvs_id)
        if loc:
            _cache[int(zvs_id)] = loc
            return loc
    except Exception as e:
        logger.error(f"get from sheets failed: {e}")
    return None
