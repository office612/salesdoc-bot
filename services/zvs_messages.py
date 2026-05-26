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
    logger.info(f"[zvs_messages] CACHED #{zvs_id} → ({chat_id}, {message_id})")
    # Дублируем в Sheets, чтоб после рестарта бот помнил
    try:
        ok = save_applicant_message(zvs_id, chat_id, message_id)
        logger.info(f"[zvs_messages] SHEETS SAVE #{zvs_id} → {ok}")
    except Exception as e:
        logger.error(f"[zvs_messages] save to sheets failed for #{zvs_id}: {e}")


def get(zvs_id: int):
    cached = _cache.get(int(zvs_id))
    if cached:
        logger.info(f"[zvs_messages] GET #{zvs_id} → cache hit {cached}")
        return cached
    logger.info(f"[zvs_messages] GET #{zvs_id} → cache miss, querying sheets")
    try:
        loc = get_applicant_message(zvs_id)
        if loc:
            _cache[int(zvs_id)] = loc
            logger.info(f"[zvs_messages] GET #{zvs_id} → sheets hit {loc}")
            return loc
        logger.warning(f"[zvs_messages] GET #{zvs_id} → not found in sheets")
    except Exception as e:
        logger.error(f"[zvs_messages] get from sheets failed for #{zvs_id}: {e}")
    return None
