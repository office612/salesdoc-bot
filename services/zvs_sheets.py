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

# То, что видит пользователь в самой таблице — на русском
HEADER = [
    "№", "Создано", "TG ID", "Имя",
    "Сумма", "На что", "Счёт",
    "Статус", "Решено", "Комментарий",
    "Дней в ожидании",
]
# Внутренние ключи (то же в том же порядке) — для словарей в коде
KEYS = [
    "id", "created_at", "telegram_id", "name",
    "amount", "purpose", "account",
    "status", "decided_at", "decision_comment",
    "days_waiting",
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
COL_DAYS = 11

# Формула «дней в ожидании»: парсим B (дата DD.MM.YYYY HH:MM) → если статус Ожидает, считаем
# Иначе пусто.
def _days_formula(row: int) -> str:
    return (
        f'=IF(H{row}="Ожидает",'
        f'TODAY()-DATE(VALUE(MID(B{row},7,4)),VALUE(MID(B{row},4,2)),VALUE(MID(B{row},1,2))),'
        f'"")'
    )


def _spreadsheet_id() -> str:
    sid = os.getenv("ZVS_SPREADSHEET_ID", "").strip()
    if not sid:
        raise RuntimeError("ZVS_SPREADSHEET_ID не задан в env")
    return sid


def get_zvs_sheet():
    """Получить лист requests, создать если нет. При создании настраивает стили + сводку."""
    ss = get_client().open_by_key(_spreadsheet_id())
    try:
        return ss.worksheet(ZVS_SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=ZVS_SHEET_NAME, rows=5000, cols=len(HEADER))
        ws.append_row(HEADER, value_input_option="USER_ENTERED")
        logger.info(f"Создан лист {ZVS_SHEET_NAME}")
        try:
            _apply_zvs_styling(ss, ws)
            _apply_conditional_formatting(ss, ws)
            _setup_summary_sheet(ss)
            _apply_protections(ss, ws)
            logger.info("Стили, сводка и защита применены")
        except Exception as e:
            logger.error(f"Не удалось применить стили: {e}", exc_info=True)
        return ws


def _apply_zvs_styling(ss, ws):
    """Базовый визуал: шапка жирная, замороженная; формат сумм; ширина колонок."""
    # Замораживаем первую строку
    ws.freeze(rows=1)

    # Жирная шапка на синем фоне, белый текст, по центру
    header_range = f"A1:{chr(ord('A') + len(HEADER) - 1)}1"
    ws.format(header_range, {
        "backgroundColor": {"red": 0.15, "green": 0.32, "blue": 0.59},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 11,
        },
    })

    # Сумма (колонка E) — числовой формат с разделителями + "тг"
    ws.format("E2:E", {
        "numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'},
        "horizontalAlignment": "RIGHT",
    })

    # Дней в ожидании (колонка K) — по центру, жирно если число
    ws.format("K2:K", {
        "horizontalAlignment": "CENTER",
        "textFormat": {"bold": True},
    })

    # Статус (колонка H) — по центру, жирно
    ws.format("H2:H", {
        "horizontalAlignment": "CENTER",
        "textFormat": {"bold": True},
    })

    # Ширины колонок (через batch_update)
    sheet_id = ws.id
    widths = [
        (0, 50),    # № — узко
        (1, 130),   # Создано
        (2, 110),   # TG ID
        (3, 160),   # Имя
        (4, 120),   # Сумма
        (5, 280),   # На что — широко
        (6, 90),    # Счёт
        (7, 110),   # Статус
        (8, 130),   # Решено
        (9, 280),   # Комментарий — широко
        (10, 90),   # Дней
    ]
    requests = []
    for col_idx, px in widths:
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex": col_idx + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })
    if requests:
        ss.batch_update({"requests": requests})


def _apply_conditional_formatting(ss, ws):
    """Цветные статусы: Одобрено зелёный, Ожидает жёлтый, Отклонено красный, Доработка синий."""
    sheet_id = ws.id
    # Колонка H (индекс 7) — статус
    status_range = {
        "sheetId": sheet_id,
        "startRowIndex": 1,  # пропускаем шапку
        "endRowIndex": 5000,
        "startColumnIndex": 7,
        "endColumnIndex": 8,
    }
    rules = [
        ("Одобрено",     {"red": 0.72, "green": 0.88, "blue": 0.72}),  # светло-зелёный
        ("Ожидает",      {"red": 1.00, "green": 0.93, "blue": 0.70}),  # светло-жёлтый
        ("Отклонено",    {"red": 0.96, "green": 0.78, "blue": 0.76}),  # светло-красный
        ("На доработку", {"red": 0.78, "green": 0.86, "blue": 0.96}),  # светло-синий
    ]
    requests = []
    for value, color in rules:
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [status_range],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": value}],
                        },
                        "format": {
                            "backgroundColor": color,
                            "textFormat": {"bold": True},
                        },
                    },
                },
                "index": 0,
            }
        })

    # Колонка K (дней в ожидании) — красный если > 3 дней
    days_range = {
        "sheetId": sheet_id,
        "startRowIndex": 1,
        "endRowIndex": 5000,
        "startColumnIndex": 10,
        "endColumnIndex": 11,
    }
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [days_range],
                "booleanRule": {
                    "condition": {
                        "type": "NUMBER_GREATER",
                        "values": [{"userEnteredValue": "3"}],
                    },
                    "format": {
                        "backgroundColor": {"red": 0.96, "green": 0.78, "blue": 0.76},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 0.6, "green": 0, "blue": 0}},
                    },
                },
            },
            "index": 0,
        }
    })

    ss.batch_update({"requests": requests})


def _setup_summary_sheet(ss):
    """Лист «Итоги» с автосводкой через формулы. Создаётся 1 раз."""
    try:
        ss.worksheet("Итоги")
        return  # уже есть
    except gspread.WorksheetNotFound:
        pass

    ws = ss.add_worksheet(title="Итоги", rows=50, cols=6)

    # Формулы — синтаксис под русскую локаль Sheets (разделитель `;` вместо `,`).
    # Все статистики — за всё время (без привязки к месяцу), потому что
    # дата в колонке B хранится как строка "DD.MM.YYYY HH:MM", фильтр по EOMONTH
    # с такой строкой не работает.
    data = [
        ["📊 Сводка по ЗВС", "", "", "", "", ""],
        ["Обновляется автоматически при новых заявках", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ["📋 За всё время", "", "", "", "", ""],
        ["Заявок всего",      '=COUNTA(requests!A2:A)', "", "", "", ""],
        ["Одобрено (шт)",     '=COUNTIF(requests!H:H; "Одобрено")', "", "", "", ""],
        ["Одобрено (тг)",     '=SUMIF(requests!H:H; "Одобрено"; requests!E:E)', "", "", "", ""],
        ["Ожидает (шт)",      '=COUNTIF(requests!H:H; "Ожидает")', "", "", "", ""],
        ["Ожидает (тг)",      '=SUMIF(requests!H:H; "Ожидает"; requests!E:E)', "", "", "", ""],
        ["Отклонено (шт)",    '=COUNTIF(requests!H:H; "Отклонено")', "", "", "", ""],
        ["На доработку (шт)", '=COUNTIF(requests!H:H; "На доработку")', "", "", "", ""],
        ["", "", "", "", "", ""],
        ["🏦 По счетам (одобрено)", "", "", "", "", ""],
        ["Халык",   '=SUMIFS(requests!E:E; requests!H:H; "Одобрено"; requests!G:G; "халык")', "", "", "", ""],
        ["Каспи",   '=SUMIFS(requests!E:E; requests!H:H; "Одобрено"; requests!G:G; "каспи")', "", "", "", ""],
        ["Наличка", '=SUMIFS(requests!E:E; requests!H:H; "Одобрено"; requests!G:G; "Наличка")', "", "", "", ""],
        ["", "", "", "", "", ""],
        ["🏆 Топ заявителей (одобрено)", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ['=IFERROR(QUERY(requests!D2:H; "select D, sum(E) where H=\'Одобрено\' group by D order by sum(E) desc label D \'Сотрудник\', sum(E) \'Сумма\'"; 0); "Пока нет одобренных заявок")', "", "", "", "", ""],
    ]
    ws.update("A1:F" + str(len(data)), data, value_input_option="USER_ENTERED")

    # Стили: заголовки разделов жирные
    ws.format("A1", {
        "textFormat": {"bold": True, "fontSize": 16},
    })
    ws.format("A2", {
        "textFormat": {"italic": True, "foregroundColor": {"red": 0.5, "green": 0.5, "blue": 0.5}},
    })
    # Заголовки разделов — строки 4, 13, 18 после обновления
    for r in (4, 13, 18):
        ws.format(f"A{r}", {
            "textFormat": {"bold": True, "fontSize": 13},
            "backgroundColor": {"red": 0.92, "green": 0.94, "blue": 0.98},
        })

    # Суммы — числовой формат с тг
    ws.format("B7", {"numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'}})    # Одобрено (тг)
    ws.format("B9", {"numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'}})    # Ожидает (тг)
    ws.format("B14:B16", {"numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'}})  # По счетам

    # Ширины
    sheet_id = ws.id
    ss.batch_update({"requests": [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 180},
            "fields": "pixelSize",
        }},
    ]})


def _apply_protections(ss, ws):
    """Защита служебных колонок: №, Создано, TG ID, Статус, Решено, Комментарий, Дней."""
    sheet_id = ws.id
    # Колонки для защиты (0-based: A=0, B=1, ...): A, B, C, H, I, J, K
    protected_cols = [0, 1, 2, 7, 8, 9, 10]
    requests = []
    for col in protected_cols:
        requests.append({
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": sheet_id,
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                    },
                    "description": "ZVS bot: только бот пишет",
                    "warningOnly": True,  # мягкая защита — Sheets предупредит, но пустит
                }
            }
        })
    if requests:
        ss.batch_update({"requests": requests})


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
        new_row_num = next_id + 1  # +1 потому что шапка занимает строку 1
        ws.append_row([
            str(next_id),
            _now_str(),
            str(telegram_id),
            name,
            int(amount),  # как число — чтоб формулы и форматирование работали
            purpose,
            account,
            "Ожидает",
            "",
            "",
            _days_formula(new_row_num),
        ], value_input_option="USER_ENTERED")
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
    """Получить заявку по ID. Возвращает dict с английскими ключами."""
    try:
        ws = get_zvs_sheet()
        row_num = find_row_by_id(zvs_id)
        if not row_num:
            return None
        row = ws.row_values(row_num)
        row = row + [""] * (len(KEYS) - len(row))
        return dict(zip(KEYS, row))
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
                row_padded = row + [""] * (len(KEYS) - len(row))
                result.append(dict(zip(KEYS, row_padded)))
        result.reverse()
        return result[:limit]
    except Exception as e:
        logger.error(f"get_user_requests {telegram_id}: {e}")
        return []
