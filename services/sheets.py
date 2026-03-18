import gspread
import logging
import json
import os
from datetime import datetime
import pytz
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, MONTH_SHEETS, TIMEZONE

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DATA_START_ROW = 7

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

COL_START_PERIOD = 19
COL_ACT_DATE     = 20
COL_ACT_PRICE    = 21
COL_STATUS       = 22


def get_client():
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(sheet_name: str):
    gc = get_client()
    ss = gc.open_by_key(SPREADSHEET_ID)
    return ss.worksheet(sheet_name)


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
        logger.error(f'get_all_values {sheet_name}: {e}')
        return []


async def add_payment(data: dict) -> int:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    month_num = data.get('month')
    if month_num:
        sheet_name = MONTH_SHEETS.get(int(month_num), MONTH_SHEETS[now.month])
    else:
        sheet_name = MONTH_SHEETS[now.month]

    ws = get_sheet(sheet_name)
    n = get_next_row(ws)

    qty    = data.get('qty', 0)
    price  = data.get('price', 0)
    amount = data.get('amount', qty * price)

    row = [''] * 23

    row[COL_DATE]    = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    row[COL_COMPANY] = data.get('client', '')
    row[COL_ARTICLE] = data.get('category_label', data.get('category', ''))
    row[COL_LICENSE] = data.get('license_type', '')
    row[COL_QTY]     = qty
    row[COL_MANAGER] = data.get('manager', '')
    row[COL_TARIFF]  = data.get('period', '')
    row[COL_PRICE]   = price
    row[COL_PERIOD]  = _period_to_num(data.get('period', ''))
    row[COL_AMOUNT]  = amount
    row[COL_BANK]    = data.get('bank', '')
    row[COL_SEATED]  = 'Нет'
    row[COL_FACT]    = data.get('fact_amount', '')

    start_m = data.get('start_month', '')
    if start_m:
        row[COL_START_PERIOD] = MONTH_SHEETS.get(int(start_m), '')

    row[COL_ACT_DATE]  = data.get('activation_date', '')
    row[COL_ACT_PRICE] = data.get('act_price', '') or ''

    cat = data.get('category', '')
    if cat in ('nov_vnedrenie', 'nov_integr', 'usluga'):
        row[COL_STATUS] = 'Не выполнено'

    ws.update(f'A{n}:W{n}', [row])
    logger.info(f'Row {n} in {sheet_name}')
    return n


async def confirm_payment(row_num: int, sheet_name: str, seated: str = 'Да') -> bool:
    try:
        ws = get_sheet(sheet_name)
        ws.update_cell(row_num, COL_SEATED + 1, seated)
        return True
    except Exception as e:
        logger.error(f'confirm_payment: {e}')
        return False


def get_payments_for_period(sheet_name: str, start_row: int = DATA_START_ROW) -> list:
    try:
        ws = get_sheet(sheet_name)
        all_vals = ws.get_all_values()
        result = []
        for i in range(start_row - 1, len(all_vals)):
            row = all_vals[i]
            if any(row):
                result.append({'row_num': i + 1, 'data': row})
        return result
    except Exception as e:
        logger.error(f'get_payments_for_period: {e}')
        return []


def _period_to_num(period: str) -> int:
    mapping = {
        '10 дней':    0,
        '20 дней':    0,
        'Месячный':   1,
        '3 месячный': 3,
        '6 месячный': 6,
        '12 месяцев': 12,
    }
    return mapping.get(period, 1)
