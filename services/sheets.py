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

_client: Optional[gspread.Client] = None
_spreadsheet: Optional[gspread.Spreadsheet] = None


def get_client() -> gspread.Client:
    global _client
    if _client is None:
        google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if google_creds_json:
            creds_dict = json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_spreadsheet() -> gspread.Spreadsheet:
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = get_client().open_by_key(SPREADSHEET_ID)
    return _spreadsheet


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


def find_last_row(ws: gspread.Worksheet) -> int:
    col_a = ws.col_values(1)
    return len(col_a) + 1


def add_payment(data: dict) -> int:
    ws = get_current_sheet()
    row_num = find_last_row(ws)
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%d.%m.%Y")
    row = [
        today,
        data.get("company", ""),
        data.get("category_raw", ""),
        data.get("license_type", ""),
        data.get("license_qty", ""),
        data.get("manager", ""),
        data.get("license_rate", ""),
        data.get("price", ""),
        data.get("period", ""),
        data.get("amount", ""),
        data.get("bank", ""),
        "Net",
        data.get("amount", ""),
        "",
        "",
        "",
        data.get("comment", ""),
        "",
    ]
    ws.insert_row(row, row_num)
    logger.info(f"Added payment row {row_num}: {data.get('company')} - {data.get('amount')}")
    return row_num


def confirm_payment(row_num: int, month: int) -> bool:
    try:
        ws = get_sheet_by_month(month)
        ws.update_cell(row_num, 12, "Yes")
        logger.info(f"Confirmed payment row {row_num}")
        return True
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        return False


def get_payments_for_period(start_date: date, end_date: date) -> list[dict]:
    tz = pytz.timezone(TIMEZONE)
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
            for i, row in enumerate(rows, start=1):
                if not row or not row[0]:
                    continue
                try:
                    row_date = datetime.strptime(row[0], "%d.%m.%Y").date()
                except ValueError:
                    continue
                if start_date <= row_date <= end_date:
                    payments.append({
                        "row_num": i,
                        "month": month,
                        "date": row_date,
                        "company": row[1] if len(row) > 1 else "",
                        "category": row[2] if len(row) > 2 else "",
                        "manager": row[5] if len(row) > 5 else "",
                        "amount": _parse_amount(row[9]) if len(row) > 9 else 0,
                        "seated": row[11] if len(row) > 11 else "Net",
                    })
        except Exception as e:
            logger.warning(f"Error reading sheet month {month}: {e}")
    return sorted(payments, key=lambda x: x["date"], reverse=True)


def _parse_amount(val: str) -> int:
    try:
        return int(str(val).replace(" ", "").replace(",", ""))
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
        logger.error(f"Error getting user: {e}")
    return None


def register_user(telegram_id: int, name: str, role: str) -> bool:
    try:
        ws = get_or_create_users_sheet()
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
        ws.append_row([str(telegram_id), name, role, now])
        return True
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        return False
