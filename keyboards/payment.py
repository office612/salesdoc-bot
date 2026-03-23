from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS, MONTH_SHEETS, PRICES_NEW, PRICES_OLD


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
    client_type = "\u043d\u043e\u0432\u044b\u0439" if is_new else "\u0441\u0442\u0430\u0440\u044b\u0439"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f'OK {price:,} x {qty} = {total:,} \u0442\u0433 ({client_type})',
            callback_data=f'price_ok:{price}'
        )],
        [InlineKeyboardButton(text='\u0412\u0432\u0435\u0441\u0442\u0438 \u0446\u0435\u043d\u0443 \u0432\u0440\u0443\u0447\u043d\u0443\u044e', callback_data='price_manual')],
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
        [InlineKeyboardButton(text='\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c', callback_data='pay_confirm'),
         InlineKeyboardButton(text='\u041e\u0442\u043c\u0435\u043d\u0430', callback_data='cancel')],
    ])


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='\u041f\u0440\u043e\u043f\u0443\u0441\u0442\u0438\u0442\u044c', callback_data='skip')],
        [InlineKeyboardButton(text='\u041e\u0442\u043c\u0435\u043d\u0430', callback_data='cancel')],
    ])


def months_kb() -> InlineKeyboardMarkup:
    rows = []
    items = list(MONTH_SHEETS.items())
    for i in range(0, len(items), 3):
        row = [InlineKeyboardButton(text=name, callback_data=f'month:{num}')
               for num, name in items[i:i+3]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='\u041e\u0442\u043c\u0435\u043d\u0430', callback_data='cancel')])
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
        [InlineKeyboardButton(text='\u0414\u0430, \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d', callback_data='activated:yes')],
        [InlineKeyboardButton(text='\u041d\u0435\u0442, \u0435\u0449\u0451 \u043d\u0435 \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d', callback_data='activated:no')],
    ])


def act_period_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='10 \u0434\u043d\u0435\u0439 3 000 \u0442\u0433/\u043b\u0438\u0446', callback_data='act_period:10:3000')],
        [InlineKeyboardButton(text='20 \u0434\u043d\u0435\u0439 4 000 \u0442\u0433/\u043b\u0438\u0446', callback_data='act_period:20:4000')],
        [InlineKeyboardButton(text='\u041f\u043e\u043b\u043d\u044b\u0439 \u043c\u0435\u0441\u044f\u0446 7 000 \u0442\u0433/\u043b\u0438\u0446', callback_data='act_period:30:7000')],
    ])


def package_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='\ud83d\udce6 \u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442 \u2014 99 000 \u0442\u0433', callback_data='pkg:99000')],
        [InlineKeyboardButton(text='\ud83d\udce6 \u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442+ \u2014 199 000 \u0442\u0433', callback_data='pkg:199000')],
        [InlineKeyboardButton(text='\u2b50 \u041f\u0440\u0435\u043c\u0438\u0443\u043c \u2014 599 000 \u0442\u0433', callback_data='pkg:599000')],
        [InlineKeyboardButton(text='\u274c \u041e\u0442\u043c\u0435\u043d\u0430', callback_data='cancel')],
    ])


def managers_kb() -> InlineKeyboardMarkup:
    from config import EMPLOYEES, LEADER
    all_mgrs = [LEADER] + [m for m in EMPLOYEES['managers'] if m != LEADER]
    rows = []
    for i in range(0, len(all_mgrs), 2):
        row = [InlineKeyboardButton(text=f'\ud83d\udc64 {n}', callback_data=f'mgr:{n}')
               for n in all_mgrs[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='\u274c \u041e\u0442\u043c\u0435\u043d\u0430', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

