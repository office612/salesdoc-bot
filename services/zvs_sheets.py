"""Работа с Google Sheets для ЗВС-бота — НЕДЕЛЬНАЯ организация.

Каждая неделя — отдельный лист. Неделя: Вт 00:00 → Пн 23:59.
- Заявка поданная во вторник → новая неделя
- Заявка в понедельник → ещё текущая неделя

Структура таблицы:
- «Итоги»                — сводка текущей недели (формулы ссылаются на текущий лист)
- «27.05 — 02.06»        — текущая неделя
- «20.05 — 26.05»        — прошлая неделя (архив)
- «_meta»                — служебный лист со счётчиком ID

Колонки в недельном листе:
    № | Создано | TG ID | Имя | Сумма | На что | Счёт
    Статус | Решено | Комментарий | Дней в ожидании | Оплачено
"""

import logging
import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Tuple

import gspread
import pytz

from services.sheets import get_client
from config import TIMEZONE

logger = logging.getLogger(__name__)

META_SHEET_NAME = "_meta"
SUMMARY_SHEET_NAME = "Итоги"

# Шапка
HEADER = [
    "№", "Создано", "TG ID", "Имя",
    "Сумма", "На что", "Счёт",
    "Статус", "Решено", "Комментарий",
    "Дней в ожидании", "Оплачено",
]
KEYS = [
    "id", "created_at", "telegram_id", "name",
    "amount", "purpose", "account",
    "status", "decided_at", "decision_comment",
    "days_waiting", "paid",
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
COL_PAID = 12

# Cache: {zvs_id: (week_label, row_num)} — чтобы не искать по всем листам
_location_cache: Dict[int, Tuple[str, int]] = {}


# ────────────────────────────────────────────────────────────
# Базовое: подключение, недельная логика
# ────────────────────────────────────────────────────────────

def _spreadsheet_id() -> str:
    sid = os.getenv("ZVS_SPREADSHEET_ID", "").strip()
    if not sid:
        raise RuntimeError("ZVS_SPREADSHEET_ID не задан в env")
    return sid


def _ss():
    return get_client().open_by_key(_spreadsheet_id())


def _now() -> datetime:
    return datetime.now(pytz.timezone(TIMEZONE))


def _now_str() -> str:
    return _now().strftime("%d.%m.%Y %H:%M")


def _week_tuesday(d: date) -> date:
    """Вторник той недели, к которой относится дата d.
    Цикл: Вт→Пн. Если d — это Вт, возвращаем сам d. Если Пн, возвращаем Вт прошлой недели."""
    # weekday: Mon=0, Tue=1, ..., Sun=6
    days_since_tuesday = (d.weekday() - 1) % 7
    return d - timedelta(days=days_since_tuesday)


def get_week_label(d: Optional[date] = None) -> str:
    """Название недельного листа: '27.05 — 02.06'."""
    if d is None:
        d = _now().date()
    tuesday = _week_tuesday(d)
    monday = tuesday + timedelta(days=6)
    return f"{tuesday.strftime('%d.%m')} — {monday.strftime('%d.%m')}"


def _days_formula(row: int) -> str:
    """Формула «дней в ожидании»: если статус Ожидает — считает с даты создания."""
    return (
        f'=IF(H{row}="Ожидает";'
        f'TODAY()-DATE(VALUE(MID(B{row};7;4));VALUE(MID(B{row};4;2));VALUE(MID(B{row};1;2)));'
        f'"")'
    )


# ────────────────────────────────────────────────────────────
# _meta — счётчик ID
# ────────────────────────────────────────────────────────────

def _get_meta_sheet():
    ss = _ss()
    try:
        return ss.worksheet(META_SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=META_SHEET_NAME, rows=10, cols=2)
        ws.update("A1:B1", [["next_zvs_id", "1"]])
        # Прячем лист от глаз пользователя
        try:
            ss.batch_update({"requests": [{
                "updateSheetProperties": {
                    "properties": {"sheetId": ws.id, "hidden": True},
                    "fields": "hidden",
                }
            }]})
        except Exception:
            pass
        return ws


def _next_zvs_id() -> int:
    """Атомарно (более-менее) получить следующий ID и записать +1 в _meta."""
    ws = _get_meta_sheet()
    try:
        val = ws.acell("B1").value
        current = int(val) if val and val.isdigit() else 1
    except Exception:
        current = 1
    try:
        ws.update_acell("B1", str(current + 1))
    except Exception as e:
        logger.error(f"_next_zvs_id update failed: {e}")
    return current


# ────────────────────────────────────────────────────────────
# Недельный лист — создание/получение
# ────────────────────────────────────────────────────────────

def get_week_sheet(d: Optional[date] = None):
    """Получить или создать недельный лист. Если новый — оформить стили + сводку."""
    label = get_week_label(d)
    ss = _ss()
    try:
        return ss.worksheet(label)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=label, rows=200, cols=20)
        ws.append_row(HEADER, value_input_option="USER_ENTERED")
        try:
            _apply_styling(ss, ws)
            _apply_conditional_formatting(ss, ws)
            _setup_data_validation(ss, ws)
            _apply_inline_summary(ss, ws, label)  # сводка справа от данных
            logger.info(f"Создан недельный лист {label}")
        except Exception as e:
            logger.error(f"Стили для {label}: {e}")
        # Обновляем «Итоги» чтоб ссылались на новый текущий лист
        try:
            _refresh_summary(ss, label)
        except Exception as e:
            logger.error(f"Refresh summary: {e}")
        return ws


def get_current_week_sheet():
    return get_week_sheet()


# ────────────────────────────────────────────────────────────
# CRUD заявок
# ────────────────────────────────────────────────────────────

def create_request(telegram_id: int, name: str, amount: int, purpose: str, account: str) -> Optional[int]:
    """Создать заявку в текущем недельном листе. Возвращает её ID."""
    try:
        ws = get_current_week_sheet()
        zvs_id = _next_zvs_id()
        # Найдём номер новой строки
        col_a = ws.col_values(1)
        new_row_num = len(col_a) + 1
        ws.append_row([
            str(zvs_id),
            _now_str(),
            str(telegram_id),
            name,
            int(amount),
            purpose,
            account,
            "Ожидает",
            "",   # Решено
            "",   # Комментарий
            _days_formula(new_row_num),
            "",   # Оплачено
        ], value_input_option="USER_ENTERED")
        _location_cache[zvs_id] = (ws.title, new_row_num)
        logger.info(f"ZVS #{zvs_id} → {amount} тг ({account}) | лист {ws.title}")
        return zvs_id
    except Exception as e:
        logger.error(f"create_request: {e}", exc_info=True)
        return None


def _find_location(zvs_id: int) -> Optional[Tuple[str, int]]:
    """Найти (week_label, row_num) для заявки. Сначала cache, потом полный поиск."""
    cached = _location_cache.get(zvs_id)
    if cached:
        return cached
    # Линейный поиск по всем weekly листам
    ss = _ss()
    target = str(zvs_id).strip()
    for ws in ss.worksheets():
        if ws.title in (META_SHEET_NAME, SUMMARY_SHEET_NAME):
            continue
        try:
            ids = ws.col_values(1)
            for i, v in enumerate(ids):
                if str(v).strip() == target:
                    loc = (ws.title, i + 1)
                    _location_cache[zvs_id] = loc
                    return loc
        except Exception:
            continue
    return None


def get_request(zvs_id: int) -> Optional[Dict]:
    """Получить заявку по ID. Ищет по всем недельным листам."""
    loc = _find_location(zvs_id)
    if not loc:
        return None
    week_label, row_num = loc
    try:
        ws = _ss().worksheet(week_label)
        row = ws.row_values(row_num)
        row = row + [""] * (len(KEYS) - len(row))
        return dict(zip(KEYS, row))
    except Exception as e:
        logger.error(f"get_request {zvs_id}: {e}")
        return None


def update_decision(zvs_id: int, status: str, comment: str = "") -> bool:
    """Обновить статус заявки."""
    loc = _find_location(zvs_id)
    if not loc:
        logger.warning(f"update_decision: заявка #{zvs_id} не найдена")
        return False
    week_label, row_num = loc
    try:
        ws = _ss().worksheet(week_label)
        ws.update_cell(row_num, COL_STATUS, status)
        ws.update_cell(row_num, COL_DECIDED, _now_str())
        if comment:
            ws.update_cell(row_num, COL_COMMENT, comment)
        logger.info(f"ZVS #{zvs_id} → {status} | лист {week_label}")
        return True
    except Exception as e:
        logger.error(f"update_decision {zvs_id}: {e}", exc_info=True)
        return False


def get_user_requests(telegram_id: int, limit: int = 10) -> List[Dict]:
    """Заявки конкретного юзера — собираем по всем недельным листам."""
    ss = _ss()
    target = str(telegram_id).strip()
    result: List[Dict] = []
    # Обходим листы в обратном порядке (новые сверху)
    for ws in reversed(ss.worksheets()):
        if ws.title in (META_SHEET_NAME, SUMMARY_SHEET_NAME):
            continue
        try:
            rows = ws.get_all_values()
            for row in rows[1:]:
                if len(row) < 3:
                    continue
                if str(row[2]).strip() == target:
                    row_padded = row + [""] * (len(KEYS) - len(row))
                    result.append(dict(zip(KEYS, row_padded)))
                    if len(result) >= limit * 2:  # с запасом
                        break
        except Exception:
            continue
        if len(result) >= limit * 2:
            break
    # Сортируем по дате создания (поле created_at — строка DD.MM.YYYY HH:MM)
    def _ts(r):
        try:
            return datetime.strptime(r.get("created_at", ""), "%d.%m.%Y %H:%M")
        except Exception:
            return datetime.min
    result.sort(key=_ts, reverse=True)
    return result[:limit]


# ────────────────────────────────────────────────────────────
# Стили + условное форматирование + валидация
# ────────────────────────────────────────────────────────────

def _apply_styling(ss, ws):
    """Базовый визуал недельного листа."""
    ws.freeze(rows=1)
    last_col_letter = chr(ord('A') + len(HEADER) - 1)
    ws.format(f"A1:{last_col_letter}1", {
        "backgroundColor": {"red": 0.15, "green": 0.32, "blue": 0.59},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True, "fontSize": 11,
        },
    })
    ws.format("E2:E", {
        "numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'},
        "horizontalAlignment": "RIGHT",
    })
    for col in ("H", "K", "L"):
        ws.format(f"{col}2:{col}", {
            "horizontalAlignment": "CENTER",
            "textFormat": {"bold": True},
        })

    widths = [
        (0, 50), (1, 130), (2, 110), (3, 160), (4, 120), (5, 280),
        (6, 90), (7, 110), (8, 130), (9, 280), (10, 90), (11, 110),
    ]
    requests = []
    for col_idx, px in widths:
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws.id, "dimension": "COLUMNS",
                    "startIndex": col_idx, "endIndex": col_idx + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })
    if requests:
        ss.batch_update({"requests": requests})


def _apply_conditional_formatting(ss, ws):
    """Цвета: Одобрено зелёный / Ожидает жёлтый / Отклонено красный / Доработка синий.
    Дней>3 — красный. Оплачено=Да — зелёный."""
    sheet_id = ws.id
    status_range = {
        "sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 200,
        "startColumnIndex": 7, "endColumnIndex": 8,
    }
    rules = [
        ("Одобрено",     {"red": 0.72, "green": 0.88, "blue": 0.72}),
        ("Ожидает",      {"red": 1.00, "green": 0.93, "blue": 0.70}),
        ("Отклонено",    {"red": 0.96, "green": 0.78, "blue": 0.76}),
        ("На доработку", {"red": 0.78, "green": 0.86, "blue": 0.96}),
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

    # Дней > 3 → красный
    days_range = {
        "sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 200,
        "startColumnIndex": 10, "endColumnIndex": 11,
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

    # Оплачено = Да → зелёный
    paid_range = {
        "sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 200,
        "startColumnIndex": 11, "endColumnIndex": 12,
    }
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [paid_range],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": "Да"}],
                    },
                    "format": {
                        "backgroundColor": {"red": 0.60, "green": 0.82, "blue": 0.60},
                        "textFormat": {"bold": True},
                    },
                },
            },
            "index": 0,
        }
    })

    ss.batch_update({"requests": requests})


def _apply_inline_summary(ss, ws, week_label: str):
    """Сводка ЭТОЙ недели справа от данных — колонки N и O.
    Формулы относительные к листу, ничего не нужно обновлять при ротации недель."""
    data = [
        [f"📊 Сводка недели", ""],
        [week_label, ""],
        ["", ""],
        ["Заявок всего",       '=COUNTA(A2:A)'],
        ["", ""],
        ["⏳ Ожидает (шт)",     '=COUNTIF(H:H, "Ожидает")'],
        ["⏳ Ожидает (тг)",     '=SUMIF(H:H, "Ожидает", E:E)'],
        ["", ""],
        ["✅ Одобрено (шт)",    '=COUNTIF(H:H, "Одобрено")'],
        ["✅ Одобрено (тг)",    '=SUMIF(H:H, "Одобрено", E:E)'],
        ["", ""],
        ["💰 Оплачено (шт)",    '=COUNTIF(L:L, "Да")'],
        ["💰 Оплачено (тг)",    '=SUMIF(L:L, "Да", E:E)'],
        ["", ""],
        ["❌ Отклонено (шт)",   '=COUNTIF(H:H, "Отклонено")'],
        ["🔄 На доработку (шт)",'=COUNTIF(H:H, "На доработку")'],
        ["", ""],
        ["🏦 По счетам (одобрено)", ""],
        ["Халык",   '=SUMIFS(E:E, H:H, "Одобрено", G:G, "халык")'],
        ["Каспи",   '=SUMIFS(E:E, H:H, "Одобрено", G:G, "каспи")'],
        ["Наличка", '=SUMIFS(E:E, H:H, "Одобрено", G:G, "Наличка")'],
    ]
    # Записываем в колонки N:O начиная с строки 1
    ws.update("N1:O" + str(len(data)), data, value_input_option="USER_ENTERED")

    # Стили: заголовок крупный
    ws.format("N1:O1", {
        "textFormat": {"bold": True, "fontSize": 14},
        "backgroundColor": {"red": 0.15, "green": 0.32, "blue": 0.59},
        "horizontalAlignment": "CENTER",
    })
    ws.format("N1:O1", {
        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True, "fontSize": 14},
    })
    ws.format("N2:O2", {
        "textFormat": {"italic": True},
        "horizontalAlignment": "CENTER",
    })

    # Суммы — формат тг
    for cell in ("O7", "O10", "O13", "O19", "O20", "O21"):
        ws.format(cell, {
            "numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'},
            "horizontalAlignment": "RIGHT",
            "textFormat": {"bold": True},
        })

    # Подзаголовок «По счетам»
    ws.format("N18:O18", {
        "textFormat": {"bold": True, "fontSize": 12},
        "backgroundColor": {"red": 0.92, "green": 0.94, "blue": 0.98},
    })

    # Ширина колонок N и O
    sheet_id = ws.id
    ss.batch_update({"requests": [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 13, "endIndex": 14},
            "properties": {"pixelSize": 200},
            "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 14, "endIndex": 15},
            "properties": {"pixelSize": 130},
            "fields": "pixelSize",
        }},
    ]})


def _setup_data_validation(ss, ws):
    """Колонка «Оплачено» — выпадающий список Да/Нет/пусто.
    Бухгалтер кликнет в ячейку и выберет."""
    sheet_id = ws.id
    requests = [{
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 200,
                "startColumnIndex": 11, "endColumnIndex": 12,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "Да"},
                        {"userEnteredValue": "Нет"},
                    ],
                },
                "showCustomUi": True,
                "strict": False,
            }
        }
    }]
    ss.batch_update({"requests": requests})


# ────────────────────────────────────────────────────────────
# Лист «Итоги» — сводка текущей недели
# ────────────────────────────────────────────────────────────

def _refresh_summary(ss, week_label: str):
    """Пересоздать формулы в Итогах так, чтоб ссылались на актуальный недельный лист."""
    try:
        ws = ss.worksheet(SUMMARY_SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=SUMMARY_SHEET_NAME, rows=50, cols=6)

    # Имя листа в одинарных кавычках (там есть пробелы и тире)
    sheet_ref = f"'{week_label}'"

    data = [
        ["📊 Сводка ЗВС — текущая неделя", "", "", "", "", ""],
        [f"Неделя: {week_label}", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ["📋 Заявки этой недели", "", "", "", "", ""],
        ["Всего",              f'=COUNTA({sheet_ref}!A2:A)', "", "", "", ""],
        ["Ожидает (шт)",       f'=COUNTIF({sheet_ref}!H:H; "Ожидает")', "", "", "", ""],
        ["Ожидает (тг)",       f'=SUMIF({sheet_ref}!H:H; "Ожидает"; {sheet_ref}!E:E)', "", "", "", ""],
        ["Одобрено (шт)",      f'=COUNTIF({sheet_ref}!H:H; "Одобрено")', "", "", "", ""],
        ["Одобрено (тг)",      f'=SUMIF({sheet_ref}!H:H; "Одобрено"; {sheet_ref}!E:E)', "", "", "", ""],
        ["Оплачено (шт)",      f'=COUNTIF({sheet_ref}!L:L; "Да")', "", "", "", ""],
        ["Оплачено (тг)",      f'=SUMIF({sheet_ref}!L:L; "Да"; {sheet_ref}!E:E)', "", "", "", ""],
        ["Отклонено (шт)",     f'=COUNTIF({sheet_ref}!H:H; "Отклонено")', "", "", "", ""],
        ["На доработку (шт)",  f'=COUNTIF({sheet_ref}!H:H; "На доработку")', "", "", "", ""],
        ["", "", "", "", "", ""],
        ["🏦 По счетам (одобрено этой недели)", "", "", "", "", ""],
        ["Халык",   f'=SUMIFS({sheet_ref}!E:E; {sheet_ref}!H:H; "Одобрено"; {sheet_ref}!G:G; "халык")', "", "", "", ""],
        ["Каспи",   f'=SUMIFS({sheet_ref}!E:E; {sheet_ref}!H:H; "Одобрено"; {sheet_ref}!G:G; "каспи")', "", "", "", ""],
        ["Наличка", f'=SUMIFS({sheet_ref}!E:E; {sheet_ref}!H:H; "Одобрено"; {sheet_ref}!G:G; "Наличка")', "", "", "", ""],
        ["", "", "", "", "", ""],
        ["🏆 Топ заявителей этой недели (одобрено)", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        [
            f"=IFERROR(QUERY({sheet_ref}!D2:H; \"select D, sum(E) where H='Одобрено' group by D order by sum(E) desc label D 'Сотрудник', sum(E) 'Сумма'\"; 0); \"Пока нет одобренных заявок\")",
            "", "", "", "", ""
        ],
    ]

    # Перед записью очищаем существующее
    try:
        ws.clear()
    except Exception:
        pass
    ws.update("A1:F" + str(len(data)), data, value_input_option="USER_ENTERED")

    # Стили заголовков
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 16}})
    ws.format("A2", {"textFormat": {"italic": True, "foregroundColor": {"red": 0.5, "green": 0.5, "blue": 0.5}}})
    for r in (4, 15, 20):
        ws.format(f"A{r}", {
            "textFormat": {"bold": True, "fontSize": 13},
            "backgroundColor": {"red": 0.92, "green": 0.94, "blue": 0.98},
        })
    # Числовые форматы для сумм
    for cell in ("B7", "B9", "B11", "B16", "B17", "B18"):
        ws.format(cell, {"numberFormat": {"type": "NUMBER", "pattern": '#,##0" тг"'}})

    # Ширины
    sheet_id = ws.id
    ss.batch_update({"requests": [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 280}, "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 180}, "fields": "pixelSize",
        }},
    ]})


# ────────────────────────────────────────────────────────────
# Инициализация при старте бота
# ────────────────────────────────────────────────────────────

def init_zvs_storage():
    """Создать _meta + текущий недельный лист + Итоги. Вызывается один раз при старте."""
    _get_meta_sheet()
    ws = get_current_week_sheet()
    # _refresh_summary вызывается из get_week_sheet при создании; если лист уже был —
    # всё равно перепишем сводку, чтоб ссылалась на правильный лист
    try:
        _refresh_summary(_ss(), ws.title)
    except Exception as e:
        logger.error(f"init refresh summary: {e}")
