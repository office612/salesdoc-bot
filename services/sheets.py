import gspread
import logging
import json
import os
from datetime import datetime, date
from typing import Optional
import pytz
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, MONTH_SHEETS, TIMEZONE

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DATA_START_ROW = 7

COL_DATE     = 0   # A
COL_COMPANY  = 1   # B
COL_ARTICLE  = 2   # C
COL_LICENSE  = 3   # D
COL_QTY      = 4   # E
COL_MANAGER  = 5   # F
COL_TARIFF   = 6   # G
COL_PRICE    = 7   # H
COL_PERIOD   = 8   # I
COL_AMOUNT   = 9   # J
COL_BANK     = 10  # K
COL_SEATED   = 11  # L
COL_FACT     = 12  # M

COL_START_PERIOD = 19  # T
COL_ACT_DATE     = 20  # U
COL_ACT_PRICE    = 21  # V
COL_STATUS       = 22  # W


def get_client() -> gspread.Client:
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)


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
        return ss.worksheet("users")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="users", rows=1000, cols=10)
        ws.append_row(["telegram_id", "name", "role", "registered_at"])
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

    qty        = int(data.get("qty", data.get("license_qty", 0)) or 0)
    price      = int(data.get("price", 0) or 0)
    period     = data.get("period", data.get("tariff", ""))
    period_num = _period_to_num(period)
    if period_num > 0:
        amount = int(qty * price * period_num)
    elif period_num == 0:
        amount = int(qty * price)
    else:
        amount = int(data.get("amount", qty * price))

    fact = data.get("fact_amount", "")
    fact_val = int(fact) if fact not in ("", None) else ""

    row = [""] * 23
    row[0]  = payment_date
    row[1]  = data.get("client", data.get("company", ""))
    row[2]  = data.get("category_label", data.get("category_raw", data.get("category", "")))
    row[3]  = data.get("license_type", data.get("license_type_raw", ""))
    row[4]  = qty
    row[5]  = data.get("manager", "")
    row[6]  = period
    row[7]  = price
    row[8]  = period_num if period_num > 0 else ""
    row[9]  = amount
    row[10] = data.get("bank", "")
    row[11] = "Нет"
    row[12] = fact_val

    start_m = data.get("start_month", "")
    row[19] = MONTH_SHEETS.get(int(start_m), "") if start_m else ""

    row[20] = data.get("activation_date", "")
    row[21] = data.get("act_price", "") or ""

    cat = data.get("category", data.get("category_raw", ""))
    if cat in ("nov_vnedrenie", "nov_integr", "usluga"):
        row[22] = "Не выполнено"

    ws.update(f"A{next_row}:W{next_row}", [row], value_input_option="USER_ENTERED")
    logger.info("Added row=" + str(next_row))
    return next_row


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
                    fact_val   = row[COL_FACT].strip()   if len(row) > COL_FACT   else ""
                    j_val      = row[COL_AMOUNT].strip() if len(row) > COL_AMOUNT else ""
                    amount     = _parse_amount(fact_val if fact_val else j_val)
                    seated_val = row[COL_SEATED].strip() if len(row) > COL_SEATED else "Нет"
                    payments.append({
                        "row_num":  i,
                        "month":    month,
                        "date":     row_date,
                        "company":  row[COL_COMPANY]  if len(row) > COL_COMPANY  else "",
                        "category": row[COL_ARTICLE]  if len(row) > COL_ARTICLE  else "",
                        "manager":  row[COL_MANAGER]  if len(row) > COL_MANAGER  else "",
                        "amount":   amount,
                        "seated":   seated_val,
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
