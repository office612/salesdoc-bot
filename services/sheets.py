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


def get_client() -> gspread.Client:
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet() -> gspread.Spreadsheet:
    return get_client().open_by_key(SPREADSHEET_ID)


def get_current_sheet() -> gspread.Worksheet:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    sheet_name = MONTH_SHEETS[now.month]
    return get_spreadsheet().worksheet(sheet_name)


def get_sheet_by_month(month: int) -> gspread.Worksheet:
    sheet_name = MONTH_SHEETS[month]
    return get_spreadsheet().worksheet(sheet_name)


def get_or_create_users_sheet() -> gspread.Worksheet:
    ss = get_spreadsheet()
    try:
        return ss.worksheet("users")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title="users", rows=100, cols=4)
        ws.append_row(["telegram_id", "name", "role", "registered_at"])
        return ws


def add_payment(data: dict) -> int:
    month = data.get("month")
    if month:
        ws = get_sheet_by_month(int(month))
    else:
        ws = get_current_sheet()

    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%d.%m.%Y")

    all_vals = ws.get_all_values()
    next_row = DATA_START_ROW
    for i in range(len(all_vals) - 1, DATA_START_ROW - 2, -1):
        if any(cell.strip() for cell in all_vals[i]):
            next_row = i + 2
            break

    j_formula = f'=ЕСЛИ(ИЛИ(E{next_row}="";H{next_row}="";I{next_row}="");"";E{next_row}*H{next_row}*I{next_row})'

    row = [
        today,
        data.get("company", ""),
        data.get("category_raw", ""),
        data.get("license_type", ""),
        int(data.get("license_qty", 0) or 0),
        data.get("manager", ""),
        data.get("tariff", ""),
        float(data.get("price", 0) or 0),
        f'=ЕСЛИ(G{next_row}="";"";ЕСЛИ(G{next_row}="Месячный";1;ЕСЛИ(G{next_row}="3 месячный";3;ЕСЛИ(G{next_row}="6 месячный";6;ЕСЛИ(G{next_row}="12 месяцев";12;1)))))',
        j_formula,
        data.get("bank", ""),
        "Нет",
    ]

    fact = data.get("fact_amount", "")
    if fact not in ("", None):
        row.append(fact)

    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Added row=" + str(next_row) + " month=" + str(month))
    return next_row


def confirm_payment(row_num: int, month: int) -> bool:
    try:
        ws = get_sheet_by_month(month)
        ws.update_cell(row_num, COL_SEATED + 1, "Да")
        return True
    except Exception as e:
        logger.error("Error confirming: " + str(e))
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
                    j_val    = row[COL_AMOUNT].strip() if len(row) > COL_AMOUNT else ""
                    amount   = _parse_amount(fact_val if fact_val else j_val)
                    seated_val = row[COL_SEATED].strip() if len(row) > COL_SEATED else "Нет"
                    payments.append({
                        "row_num":  i, "month": month, "date": row_date,
                        "company":  row[COL_COMPANY]  if len(row) > COL_COMPANY  else "",
                        "category": row[COL_ARTICLE]  if len(row) > COL_ARTICLE  else "",
                        "manager":  row[COL_MANAGER]  if len(row) > COL_MANAGER  else "",
                        "period":   row[COL_PERIOD]   if len(row) > COL_PERIOD   else "",
                        "amount":   amount,
                        "bank":     row[COL_BANK]     if len(row) > COL_BANK     else "",
                        "seated":   seated_val,
                    })
        except Exception as e:
            logger.warning("Error reading month=" + str(month) + ": " + str(e))

    return sorted(payments, key=lambda x: x["date"], reverse=True)


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
        logger.error("Error getting user: " + str(e))
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
                logger.info(f"Updated user {telegram_id} -> {name}")
                return True
        ws.append_row([str(telegram_id), name, role, now])
        logger.info(f"Registered user {telegram_id} -> {name}")
        return True
    except Exception as e:
        logger.error("Error register_user: " + str(e))
        return False

