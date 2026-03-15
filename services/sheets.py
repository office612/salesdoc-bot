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

# Структура таблицы Доходы KZ 2026:
# A=Дата B=Компания C=Статья D=Лицензии E=Кол-во F=Менеджер
# G=Тариф H=Цена I=Период J=Сумма K=Банк L=Оплата посажена
# Строки 1-6 — заголовки, данные начинаются с строки 7
DATA_START_ROW = 7  # строки 1-6 заняты заголовками

# Индексы колонок (0-based)
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


def find_last_data_row(ws: gspread.Worksheet) -> int:
    """Ищет первую пустую строку начиная с DATA_START_ROW."""
    col_a = ws.col_values(1)  # колонка A (Дата)
    # Строки 1-6 — заголовки, ищем первую пустую после них
    for i in range(DATA_START_ROW - 1, len(col_a)):
        if not str(col_a[i]).strip():
            return i + 1  # 1-based
    return len(col_a) + 1


def add_payment(data: dict) -> int:
    ws = get_current_sheet()
    row_num = find_last_data_row(ws)
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime('%d.%m.%Y')
    # Заполняем по структуре таблицы:
    # A=Дата B=Компания C=Статья D=Лицензии E=Кол-во F=Менеджер
    # G=Тариф H=Цена I=Период J=Сумма K=Банк L=Оплата посажена
    row = [
        today,                           # A - Дата
        data.get('company', ''),         # B - Компания
        data.get('category_raw', ''),    # C - Статья
        data.get('license_type', ''),    # D - Лицензии
        data.get('license_qty', ''),     # E - Кол-во
        data.get('manager', ''),         # F - Менеджер
        data.get('tariff', ''),          # G - Тариф
        data.get('price', ''),           # H - Цена
        data.get('period', ''),          # I - Период
        data.get('amount', ''),          # J - Сумма
        data.get('bank', ''),            # K - Банк
        'Нет',            # L - Оплата посажена
    ]
    ws.insert_row(row, row_num)
    logger.info(f'Added payment row={row_num} company={data.get("company")} amount={data.get("amount")}')
    return row_num


def confirm_payment(row_num: int, month: int) -> bool:
    try:
        ws = get_sheet_by_month(month)
        ws.update_cell(row_num, COL_SEATED + 1, 'Да')  # колонка L
        logger.info(f'Confirmed payment row={row_num}')
        return True
    except Exception as e:
        logger.error(f'Error confirming: {e}')
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
            # Пропускаем первые 6 строк-заголовков
            data_rows = rows[DATA_START_ROW - 1:]
            for i, row in enumerate(data_rows, start=DATA_START_ROW):
                if not row or not str(row[COL_DATE]).strip():
                    continue
                try:
                    row_date = datetime.strptime(row[COL_DATE].strip(), '%d.%m.%Y').date()
                except ValueError:
                    continue
                if start_date <= row_date <= end_date:
                    amount = _parse_amount(row[COL_AMOUNT] if len(row) > COL_AMOUNT else '')
                    payments.append({
                        'row_num':  i,
                        'month':    month,
                        'date':     row_date,
                        'company':  row[COL_COMPANY]  if len(row) > COL_COMPANY  else '',
                        'category': row[COL_ARTICLE]  if len(row) > COL_ARTICLE  else '',
                        'manager':  row[COL_MANAGER]  if len(row) > COL_MANAGER  else '',
                        'period':   row[COL_PERIOD]   if len(row) > COL_PERIOD   else '',
                        'amount':   amount,
                        'bank':     row[COL_BANK]     if len(row) > COL_BANK     else '',
                        'seated':   row[COL_SEATED]   if len(row) > COL_SEATED   else 'Нет',
                    })
        except Exception as e:
            logger.warning(f'Error reading sheet month={month}: {e}')
    return sorted(payments, key=lambda x: x['date'], reverse=True)


def _parse_amount(val: str) -> int:
    try:
        clean = str(val).replace(' ', '').replace(',', '.').replace(' ', '')
        return int(float(clean))
    except (ValueError, TypeError):
        return 0


def get_user(telegram_id: int) -> Optional[dict]:
    try:
        ws = get_or_create_users_sheet()
        rows = ws.get_all_records()
        for row in rows:
            if str(row.get('telegram_id')) == str(telegram_id):
                return row
    except Exception as e:
        logger.error(f'Error getting user: {e}')
    return None


def register_user(telegram_id: int, name: str, role: str) -> bool:
    try:
        ws = get_or_create_users_sheet()
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz).strftime('%d.%m.%Y %H:%M')
        ws.append_row([str(telegram_id), name, role, now])
        return True
    except Exception as e:
        logger.error(f'Error register_user: {e}')
        return False
