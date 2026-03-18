import gspread
import logging
import json
import os
from datetime import datetime, date
import pytz
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, MONTH_SHEETS, TIMEZONE

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DATA_START_ROW = 7

# Существующие столбцы A-M
COL_DATE     = 0
COL_COMPANY  = 1
COL_ARTICLE  = 2
COL_LICENSE  = 3
COL_QTY      = 4
COL_MANAGER  = 5
COL_TARIFF   = 6
COL_PRICE    = 7
COL_PERIOD   = 8
COL_AMOUNT   = 9
COL_BANK     = 10
COL_SEATED   = 11
COL_FACT     = 12

# Новые столбцы T-W (с апреля 2026)
COL_START_PERIOD = 19
COL_ACT_DATE     = 20
COL_ACT_PRICE    = 21
COL_STATUS       = 22

USERS_SHEET = "users"


def get_client():
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet():
    gc = get_client()
    return gc.open_by_key(SPREADSHEET_ID)


def get_sheet(sheet_name: str):
    return get_spreadsheet().worksheet(sheet_name)


def get_sheet_by_month(month: int):
    sheet_name = MONTH_SHEETS.get(month)
    if not sheet_name:
        raise ValueError("Unknown month: " + str(month))
    return get_sheet(sheet_name)


def get_next_row(ws) -> int:
    all_vals = ws.get_all_values()
    for i in range(DATA_START_ROW - 1, len(all_vals)):
        if not any(all_vals[i]):
            return i + 1
    return len(all_vals) + 1


def get_all_values(sheet_name: str) -> list:
    try:
        ws = get_sheet(sheet_name)
        return ws.get_all_values()
    except Exception as e:
        logger.error("get_all_values " + sheet_name + ": " + str(e))
        return []


# ── Пользователи ──────────────────────────────────────────────
def get_user(telegram_id: int) -> dict | None:
    try:
        ws = get_sheet(USERS_SHEET)
        rows = ws.get_all_values()
        for row in rows[1:]:
            if row and str(row[0]) == str(telegram_id):
                return {
                    "telegram_id": telegram_id,
                    "name": row[1] if len(row) > 1 else "",
                    "role": row[2] if len(row) > 2 else "menedzher",
                    "approved": row[3] if len(row) > 3 else "yes",
                }
        return None
    except Exception as e:
        logger.error("get_user: " + str(e))
        return None


def register_user(telegram_id: int, name: str, role: str) -> None:
    try:
        ws = get_sheet(USERS_SHEET)
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[0]) == str(telegram_id):
                ws.update(f"A{i}:D{i}", [[str(telegram_id), name, role, "yes"]])
                return
        ws.append_row([str(telegram_id), name, role, "yes"])
    except Exception as e:
        logger.error("register_user: " + str(e))


# ── Оплаты ────────────────────────────────────────────────────
async def add_payment(data: dict) -> int:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    month_num = data.get("month")
    if month_num:
        ws = get_sheet_by_month(int(month_num))
    else:
        ws = get_sheet_by_month(now.month)

    n = get_next_row(ws)

    qty    = data.get("qty", 0)
    price  = data.get("price", 0)
    amount = data.get("amount", qty * price)

    row = [""] * 23

    row[COL_DATE]    = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    row[COL_COMPANY] = data.get("client", "")
    row[COL_ARTICLE] = data.get("category_label", data.get("category", ""))
    row[COL_LICENSE] = data.get("license_type", "")
    row[COL_QTY]     = qty
    row[COL_MANAGER] = data.get("manager", "")
    row[COL_TARIFF]  = data.get("period", "")
    row[COL_PRICE]   = price
    row[COL_PERIOD]  = _period_to_num(data.get("period", ""))
    row[COL_AMOUNT]  = amount
    row[COL_BANK]    = data.get("bank", "")
    row[COL_SEATED]  = "Нет"
    row[COL_FACT]    = data.get("fact_amount", "")

    start_m = data.get("start_month", "")
    if start_m:
        row[COL_START_PERIOD] = MONTH_SHEETS.get(int(start_m), "")

    row[COL_ACT_DATE]  = data.get("activation_date", "")
    row[COL_ACT_PRICE] = data.get("act_price", "") or ""

    cat = data.get("category", "")
    if cat in ("nov_vnedrenie", "nov_integr", "usluga"):
        row[COL_STATUS] = "Не выполнено"

    ws.update(f"A{n}:W{n}", [row])
    logger.info(f"Row {n} added")
    return n


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
                if any(row):
                    payments.append({"row_num": i, "month": month, "data": row})
        except Exception as e:
            logger.error("get_payments_for_period month=" + str(month) + ": " + str(e))

    return payments


def _period_to_num(period: str) -> int:
    mapping = {
        "10 дней":    0,
        "20 дней":    0,
        "Месячный":   1,
        "3 месячный": 3,
        "6 месячный": 6,
        "12 месяцев": 12,
    }
    return mapping.get(period, 1)
