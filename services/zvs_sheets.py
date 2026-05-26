"""Работа с Google Sheets для ЗВС-бота.

Отдельная таблица (env: ZVS_SPREADSHEET_ID), один лист «requests».
Колонки:
    id | created_at | telegram_id | name | amount | purpose | account
    status | decided_at | decision_comment
"""

import logging
import os
from datetime import datetime
from typing import Optional, List, Dict

import gspread
import pytz

from services.sheets import get_client
from config import TIMEZONE

logger = logging.getLogger(__name__)

ZVS_SHEET_NAME = "requests"

HEADER = [
    "id", "created_at", "telegram_id", "name",
    "amount", "purpose", "account",
    "status", "decided_at", "decision_comment",
]

# Колонки (1-based для gspread)
COL_ID = 1
COL_CREATED = 2
COL_TG_ID = 3
COL_NAME = 4
COL_AMOUNT = 5
COL_PURPOSE = 6
COL_ACCOUNT = 7
COL_STATUS = 8
COL_DECIDED = 9
COL_COMMENT = 10


def _spreadsheet_id() -> str:
    sid = os.getenv("ZVS_SPREADSHEET_ID", "").strip()
    if not sid:
        raise RuntimeError("ZVS_SPREADSHEET_ID не задан в env")
    return sid


def get_zvs_sheet():
    """Получить лист requests, создать если нет."""
    ss = get_client().open_by_key(_spreadsheet_id())
    try:
        return ss.worksheet(ZVS_SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=ZVS_SHEET_NAME, rows=5000, cols=len(HEADER))
        ws.append_row(HEADER)
        logger.info(f"Создан лист {ZVS_SHEET_NAME}")
        return ws


def _now_str() -> str:
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")


def create_request(
    telegram_id: int, name: str, amount: int, purpose: str, account: str,
) -> Optional[int]:
    """Создать новую заявку. Возвращает её ID."""
    try:
        ws = get_zvs_sheet()
        # Следующий ID = текущее количество строк (без шапки)
        all_vals = ws.get_all_values()
        next_id = len(all_vals)  # шапка занимает строку 1, поэтому len == id первой пустой
        ws.append_row([
            str(next_id),
            _now_str(),
            str(telegram_id),
            name,
            str(amount),
            purpose,
            account,
            "Ожидает",
            "",
            "",
        ])
        logger.info(f"ZVS #{next_id} создана: {telegram_id} → {amount} тг ({account})")
        return next_id
    except Exception as e:
        logger.error(f"create_request: {e}", exc_info=True)
        return None


def find_row_by_id(zvs_id: int) -> int:
    """Найти номер строки по ID заявки. Возвращает 0 если не нашли."""
    try:
        ws = get_zvs_sheet()
        ids = ws.col_values(COL_ID)
        for i, v in enumerate(ids):
            if str(v).strip() == str(zvs_id):
                return i + 1  # 1-based
        return 0
    except Exception as e:
        logger.error(f"find_row_by_id: {e}")
        return 0


def get_request(zvs_id: int) -> Optional[Dict]:
    """Получить заявку по ID."""
    try:
        ws = get_zvs_sheet()
        row_num = find_row_by_id(zvs_id)
        if not row_num:
            return None
        row = ws.row_values(row_num)
        # Дополняем до длины HEADER
        row = row + [""] * (len(HEADER) - len(row))
        return dict(zip(HEADER, row))
    except Exception as e:
        logger.error(f"get_request {zvs_id}: {e}")
        return None


def update_decision(zvs_id: int, status: str, comment: str = "") -> bool:
    """Обновить статус заявки. status: Одобрено / Отклонено / На доработку."""
    try:
        ws = get_zvs_sheet()
        row_num = find_row_by_id(zvs_id)
        if not row_num:
            logger.warning(f"update_decision: заявка #{zvs_id} не найдена")
            return False
        ws.update_cell(row_num, COL_STATUS, status)
        ws.update_cell(row_num, COL_DECIDED, _now_str())
        if comment:
            ws.update_cell(row_num, COL_COMMENT, comment)
        logger.info(f"ZVS #{zvs_id} → {status}")
        return True
    except Exception as e:
        logger.error(f"update_decision {zvs_id}: {e}", exc_info=True)
        return False


def get_user_requests(telegram_id: int, limit: int = 10) -> List[Dict]:
    """Заявки конкретного юзера, последние сверху."""
    try:
        ws = get_zvs_sheet()
        all_vals = ws.get_all_values()
        result = []
        for row in all_vals[1:]:
            if len(row) < 3:
                continue
            if str(row[2]).strip() == str(telegram_id):
                row_padded = row + [""] * (len(HEADER) - len(row))
                result.append(dict(zip(HEADER, row_padded)))
        result.reverse()
        return result[:limit]
    except Exception as e:
        logger.error(f"get_user_requests {telegram_id}: {e}")
        return []
