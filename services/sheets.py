import gspread
import logging
import json
import os
from datetime import datetime, date
from typing import Optional

import pytz
from google.oauth2.service_account import Credentials

from config import SPREADSHEET_ID, MONTH_SHEETS, TIMEZONE, STATUS_CATS, WRITE_ACT_COLS

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DATA_START_ROW = 7

# ── Кэш справочника (загружается один раз за сессию) ─────────
_ref_cache = {}  # {"Статьи Доходов": [...], "Менеджеры": [...], "Банки": [...]}


def _load_ref_cache():
    """Загружаем лист Справочник и кэшируем значения для валидации."""
    if _ref_cache:
        return
    try:
        ss = get_client().open_by_key(SPREADSHEET_ID)
        ws = ss.worksheet("Справочник")
        all_vals = ws.get_all_values()
        if not all_vals:
            return
        headers = [h.strip() for h in all_vals[0]]
        for col_idx, header in enumerate(headers):
            if header:
                values = []
                for row in all_vals[1:]:
                    if col_idx < len(row) and row[col_idx]:
                        values.append(row[col_idx])
                _ref_cache[header] = values
        logger.info(f"Ref cache loaded: {list(_ref_cache.keys())}")
    except Exception as e:
        logger.warning(f"Failed to load ref cache: {e}")


def _match_ref_value(value: str, ref_column: str) -> str:
    """Ищет точное значение из справочника по strip-совпадению."""
    _load_ref_cache()
    ref_values = _ref_cache.get(ref_column, [])
    val_stripped = value.strip()
    for ref_val in ref_values:
        if ref_val.strip() == val_stripped:
            return ref_val
    return value


COL_DATE = 0       # A
COL_COMPANY = 1    # B
COL_ARTICLE = 2    # C
COL_LICENSE = 3    # D
COL_QTY = 4        # E
COL_MANAGER = 5    # F
COL_TARIFF = 6     # G
COL_PRICE = 7      # H
COL_PERIOD = 8     # I
COL_AMOUNT = 9     # J
COL_BANK = 10      # K
COL_SEATED = 11    # L
COL_FACT = 12      # M
COL_LINK = 15      # P  (ссылка на скрин оплаты)
COL_START_PERIOD = 19  # T
COL_ACT_DATE = 20  # U
COL_ACT_PRICE = 21 # V
COL_STATUS = 22    # W


_gspread_client_cache = None


def get_client() -> gspread.Client:
    """Возвращает gspread клиент. Кэшируется на жизнь процесса —
    повторная авторизация HTTP+SSL handshake занимает ~1-2 сек, а это
    делалось при каждом запросе. Теперь — один раз."""
    global _gspread_client_cache
    if _gspread_client_cache is not None:
        return _gspread_client_cache
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    _gspread_client_cache = gspread.authorize(creds)
    return _gspread_client_cache


def get_spreadsheet():
    return get_client().open_by_key(SPREADSHEET_ID)


def get_sheet(sheet_name: str):
    return get_spreadsheet().worksheet(sheet_name)


def get_sheet_by_month(month: int):
    name = MONTH_SHEETS.get(month)
    if not name:
        raise ValueError("Unknown month: " + str(month))
    return get_sheet(name)


def get_current_sheet():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return get_sheet_by_month(now.month)


def get_or_create_users_sheet():
    ss = get_spreadsheet()
    try:
        ws = ss.worksheet("users")
        # Дозаполняем заголовок subscribed, если его ещё нет (для старых таблиц)
        try:
            header = ws.row_values(1)
            if len(header) < 5 or (header[4] if len(header) > 4 else "") != "subscribed":
                ws.update_cell(1, 5, "subscribed")
        except Exception:
            pass
        return ws
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="users", rows=1000, cols=10)
        ws.append_row(["telegram_id", "name", "role", "registered_at", "subscribed"])
        return ws


def _period_to_num(period: str) -> int:
    p = str(period).strip()
    if p == "Месячный":
        return 1
    elif p == "3 месячный":
        return 3
    elif p == "6 месячный":
        return 6
    elif p == "12 месяцев":
        return 12
    # Написания тарифов таблицы KG (2026-07-21) — синхронно с salesdoc_sync._period_to_months
    elif p == "месяц":
        return 1
    elif p == "3 месяц":
        return 3
    elif p == "6 месяц":
        return 6
    elif p == "12 месяц":
        return 12
    elif p == "10 дней":
        return 0
    elif p == "20 дней":
        return 0
    elif p == "Услуга":
        return -1
    elif p == "Баланс":
        return -1
    return -1


async def add_payment(data: dict) -> int:
    month_num = data.get("month")
    if month_num:
        ws = get_sheet_by_month(int(month_num))
    else:
        ws = get_current_sheet()

    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%d.%m.%Y")
    payment_date = data.get("payment_date", "").strip() or today

    col_a = ws.col_values(1)
    next_row = len(col_a) + 1

    qty_raw = data.get("qty", data.get("license_qty", 0))
    try:
        qty = int(qty_raw) if qty_raw not in ("", None) else 0
    except (ValueError, TypeError):
        qty = 0

    price_raw = data.get("price", "")
    try:
        price = int(price_raw) if price_raw not in ("", None) else 0
    except (ValueError, TypeError):
        price = 0

    period = data.get("period", data.get("tariff", ""))
    period_num = _period_to_num(period)

    # Если amount явно пустой (ручной ввод — оплата не по формуле, идёт в M),
    # столбец J оставляем пустым, чтобы не путать формульную сумму с фактом.
    explicit_amount_raw = data.get("amount", None)
    explicit_amount_is_empty = explicit_amount_raw == ""
    explicit_amount = None
    try:
        if explicit_amount_raw not in ("", None):
            explicit_amount = int(explicit_amount_raw)
    except (ValueError, TypeError):
        explicit_amount = None

    if explicit_amount_is_empty:
        amount = ""  # ручной ввод → J пусто, фактический итог пишем в M
    elif explicit_amount is not None and explicit_amount > 0:
        amount = explicit_amount
    elif period_num > 0:
        amount = int(qty * price * period_num)
    elif period_num == 0:
        amount = int(qty * price)
    else:
        amount = int(qty * price)

    # H (цена за лицензию) пустой строкой, если её явно не задавали
    price_cell = price if price_raw not in ("", None) else ""

    fact = data.get("fact_amount", "")
    fact_val = int(fact) if fact not in ("", None) else ""

    # A-M (столбцы 1-13) — основные данные
    raw_article = data.get("category_label", data.get("category_raw", data.get("category", "")))
    raw_manager = data.get("manager", "")
    raw_bank = data.get("bank", "")

    row_am = [
        payment_date,                                      # A
        data.get("client", data.get("company", "")),       # B
        _match_ref_value(raw_article, "Статьи Доходов"),   # C
        data.get("license_type", data.get("license_type_raw", "")),  # D
        qty if qty_raw not in ("", None) else "",          # E
        _match_ref_value(raw_manager, "Менеджеры"),        # F
        period,                                            # G
        price_cell,                                        # H
        period_num if period_num > 0 else "",              # I
        amount,                                            # J
        _match_ref_value(raw_bank, "Банки"),               # K
        "Нет",                                             # L
        fact_val,                                          # M
    ]

    # T-W (столбцы 20-23) — доп. поля, пропускаем N-S (формулы)
    start_m = data.get("start_month", "")
    cat = data.get("category", data.get("category_raw", ""))
    row_tw = [
        MONTH_SHEETS.get(int(start_m), "") if start_m else "",  # T
        data.get("activation_date", ""),                         # U
        data.get("act_price", "") or "",                         # V
        "Не выполнено" if cat in STATUS_CATS else "",            # W
    ]

    ws.update(f"A{next_row}:M{next_row}", [row_am], value_input_option="USER_ENTERED")
    # В таблице KG колонок T-W нет — не пишем (config.WRITE_ACT_COLS)
    if WRITE_ACT_COLS:
        ws.update(f"T{next_row}:W{next_row}", [row_tw], value_input_option="USER_ENTERED")
    logger.info("Added row=" + str(next_row))
    return next_row


def update_receipt_link(row_num: int, month: int, link: str) -> bool:
    """Записывает ссылку на скрин оплаты в столбец P."""
    try:
        ws = get_sheet_by_month(month)
        ws.update_cell(row_num, COL_LINK + 1, link)
        logger.info(f"Receipt link set: row={row_num}, link={link}")
        return True
    except Exception as e:
        logger.error(f"update_receipt_link error: {e}")
        return False


def confirm_payment(row_num: int, month: int) -> bool:
    try:
        ws = get_sheet_by_month(month)
        ws.update_cell(row_num, COL_SEATED + 1, "Да")
        return True
    except Exception as e:
        logger.error("confirm_payment: " + str(e))
        return False


def get_payments_for_period(start_date: date, end_date: date) -> list:
    payments = []
    months_needed = set()
    current = start_date
    while current <= end_date:
        months_needed.add(current.month)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    for month in months_needed:
        try:
            ws = get_sheet_by_month(month)
            rows = ws.get_all_values()
            data_rows = rows[DATA_START_ROW - 1:]
            for i, row in enumerate(data_rows, start=DATA_START_ROW):
                if not row or not str(row[COL_DATE]).strip():
                    continue
                try:
                    row_date = datetime.strptime(row[COL_DATE].strip(), "%d.%m.%Y").date()
                except ValueError:
                    continue

                if start_date <= row_date <= end_date:
                    fact_val = row[COL_FACT].strip() if len(row) > COL_FACT else ""
                    j_val = row[COL_AMOUNT].strip() if len(row) > COL_AMOUNT else ""
                    amount = _parse_amount(fact_val if fact_val else j_val)
                    seated_val = row[COL_SEATED].strip() if len(row) > COL_SEATED else "Нет"
                    payments.append({
                        "row_num": i,
                        "month": month,
                        "date": row_date,
                        "company": row[COL_COMPANY] if len(row) > COL_COMPANY else "",
                        "category": row[COL_ARTICLE] if len(row) > COL_ARTICLE else "",
                        "manager": row[COL_MANAGER] if len(row) > COL_MANAGER else "",
                        "amount": amount,
                        "seated": seated_val,
                    })
        except Exception as e:
            logger.error("get_payments_for_period month=" + str(month) + ": " + str(e))
    return payments


def _parse_amount(val: str) -> int:
    try:
        clean = str(val).replace(" ", "").replace(",", ".").replace("\u00a0", "")
        return int(float(clean))
    except (ValueError, TypeError):
        return 0


def get_user(telegram_id: int) -> Optional[dict]:
    try:
        ws = get_or_create_users_sheet()
        rows = ws.get_all_records()
        for row in rows:
            if str(row.get("telegram_id")) == str(telegram_id):
                return row
    except Exception as e:
        logger.error("get_user: " + str(e))
    return None


def register_user(telegram_id: int, name: str, role: str) -> bool:
    try:
        ws = get_or_create_users_sheet()
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[0]) == str(telegram_id):
                ws.update(f"A{i}:D{i}", [[str(telegram_id), name, role, now]])
                return True
        ws.append_row([str(telegram_id), name, role, now])
        return True
    except Exception as e:
        logger.error("register_user: " + str(e))
        return False


def mark_planted(row_num: int, month: int) -> bool:
    """Записывает 'Да' в столбец L указанной строки.

    Используется кнопкой Посажено в @SDfinansbot.
    """
    try:
        sheet_name = MONTH_SHEETS.get(month)
        if not sheet_name:
            logger.error(f"mark_planted: неизвестный месяц {month}")
            return False
        ss = get_client().open_by_key(SPREADSHEET_ID)
        ws = ss.worksheet(sheet_name)
        # Столбец L = 12-й столбец (1-based в gspread)
        ws.update_cell(int(row_num), 12, "Да")
        logger.info(f"mark_planted: строка {row_num}, лист {sheet_name} -> Да")
        return True
    except Exception as e:
        logger.error(f"mark_planted error: {e}", exc_info=True)
        return False


# ────────────────────────────────────────────────────────────
# Подписки на уведомления + лог ошибок бота
# Колонка E в листе users: "subscribed" (TRUE/FALSE). Пусто = подписан.
# ────────────────────────────────────────────────────────────

def get_user_name(telegram_id: int) -> Optional[str]:
    """Имя пользователя по tg_id — для лога ошибок."""
    user = get_user(telegram_id)
    if user:
        return user.get("name", "")
    return None


def is_subscribed(telegram_id: int) -> bool:
    """Подписан ли юзер на уведомления. По умолчанию TRUE."""
    try:
        ws = get_or_create_users_sheet()
        rows = ws.get_all_values()
        for row in rows[1:]:
            if row and str(row[0]) == str(telegram_id):
                # Колонка E (index 4) = subscribed
                if len(row) > 4:
                    val = str(row[4]).strip().upper()
                    if val == "FALSE":
                        return False
                return True
        # Юзер не в таблице (например, директор) — считаем что подписан
        return True
    except Exception as e:
        logger.error(f"is_subscribed: {e}")
        return True  # При ошибке — лучше отправить, чем потерять уведомление


def set_subscription(telegram_id: int, subscribed: bool) -> bool:
    """Переключает подписку. Возвращает True если успешно."""
    try:
        ws = get_or_create_users_sheet()
        rows = ws.get_all_values()
        val = "TRUE" if subscribed else "FALSE"
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[0]) == str(telegram_id):
                ws.update_cell(i, 5, val)  # Колонка E
                logger.info(f"set_subscription: {telegram_id} -> {val}")
                return True
        # Юзера нет — добавлять не будем (директор/случайный)
        logger.warning(f"set_subscription: юзер {telegram_id} не найден")
        return False
    except Exception as e:
        logger.error(f"set_subscription: {e}")
        return False


def get_or_create_bot_errors_sheet():
    """Лист bot_errors для логирования сбоев отправки."""
    ss = get_spreadsheet()
    try:
        return ss.worksheet("bot_errors")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="bot_errors", rows=1000, cols=6)
        ws.append_row(["timestamp", "chat_id", "name", "error_type", "details", "resolved"])
        return ws


def log_bot_error(chat_id: int, name: str, error_type: str, details: str) -> bool:
    """Пишет строку в bot_errors. Никогда не падает — только лог."""
    try:
        ws = get_or_create_bot_errors_sheet()
        tz = pytz.timezone(TIMEZONE)
        ts = datetime.now(tz).strftime("%d.%m.%Y %H:%M:%S")
        ws.append_row([ts, str(chat_id), name, error_type, details, ""])
        return True
    except Exception as e:
        logger.error(f"log_bot_error failed: {e}")
        return False
