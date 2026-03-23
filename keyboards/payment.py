from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import pytz
from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS, MONTH_SHEETS, PRICES_NEW, PRICES_OLD, TIMEZONE


def categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f'cat:{key}')]
        for key, label in CATEGORIES
    ])


def license_types_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lt, callback_data=f'lt:{lt}')]
        for lt in LICENSE_TYPES
    ])


def periods_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(PERIODS), 2):
        row = [InlineKeyboardButton(text=PERIODS[j], callback_data=f'period:{PERIODS[j]}')
               for j in range(i, min(i+2, len(PERIODS)))]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_price_kb(period: str, qty: int, is_new: bool) -> InlineKeyboardMarkup:
    prices = PRICES_NEW if is_new else PRICES_OLD
    price = prices.get(period, 0)
    total = price * qty
    client_type = "новый" if is_new else "старый"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f'OK {price:,} x {qty} = {total:,} тг ({client_type})',
            callback_data=f'price_ok:{price}'
        )],
        [InlineKeyboardButton(text='Ввести цену вручную', callback_data='price_manual')],
    ])


def banks_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(BANKS), 2):
        row = [InlineKeyboardButton(text=BANKS[j], callback_data=f'bank:{BANKS[j]}')
               for j in range(i, min(i+2, len(BANKS)))]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Записать', callback_data='pay_confirm'),
         InlineKeyboardButton(text='Отмена', callback_data='cancel')],
    ])


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Пропустить', callback_data='skip')],
        [InlineKeyboardButton(text='Отмена', callback_data='cancel')],
    ])


def months_kb() -> InlineKeyboardMarkup:
    rows = []
    items = list(MONTH_SHEETS.items())
    for i in range(0, len(items), 3):
        row = [InlineKeyboardButton(text=name, callback_data=f'month:{num}')
               for num, name in items[i:i+3]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_month_kb() -> InlineKeyboardMarkup:
    rows = []
    items = list(MONTH_SHEETS.items())
    for i in range(0, len(items), 3):
        row = [InlineKeyboardButton(text=name, callback_data=f'start_month:{num}')
               for num, name in items[i:i+3]]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def activation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Да, активирован', callback_data='activated:yes')],
        [InlineKeyboardButton(text='Нет, ещё не активирован', callback_data='activated:no')],
    ])


def act_period_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='10 дней 3 000 тг/лиц', callback_data='act_period:10:3000')],
        [InlineKeyboardButton(text='20 дней 4 000 тг/лиц', callback_data='act_period:20:4000')],
        [InlineKeyboardButton(text='Полный месяц 7 000 тг/лиц', callback_data='act_period:30:7000')],
    ])


def package_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📦 Стандарт \u2014 99 000 тг', callback_data='pkg:99000')],
        [InlineKeyboardButton(text='📦 Стандарт+ \u2014 199 000 тг', callback_data='pkg:199000')],
        [InlineKeyboardButton(text='\u2b50 Премиум \u2014 599 000 тг', callback_data='pkg:599000')],
        [InlineKeyboardButton(text='\u274c Отмена', callback_data='cancel')],
    ])


def managers_kb() -> InlineKeyboardMarkup:
    from config import EMPLOYEES, LEADER
    all_mgrs = [LEADER] + [m for m in EMPLOYEES['managers'] if m != LEADER]
    rows = []
    for i in range(0, len(all_mgrs), 2):
        row = [InlineKeyboardButton(text=f'\ud83d\udc64 {n}', callback_data=f'mgr:{n}')
               for n in all_mgrs[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='\u274c Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_date_kb() -> InlineKeyboardMarkup:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%d.%m.%Y")
    yesterday = (now - timedelta(days=1)).strftime("%d.%m.%Y")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'\ud83d\udcc5 Сегодня ({today})', callback_data=f'pdate:{today}')],
        [InlineKeyboardButton(text=f'\ud83d\udcc5 Вчера ({yesterday})', callback_data=f'pdate:{yesterday}')],
        [InlineKeyboardButton(text='\u270f\ufe0f Ввести дату', callback_data='pdate:manual')],
        [InlineKeyboardButton(text='\u274c Отмена', callback_data='cancel')],
    ])
