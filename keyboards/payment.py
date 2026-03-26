from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import calendar
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
    price_new = PRICES_NEW.get(period, 0)
    price_old = PRICES_OLD.get(period, 0)
    total_new = price_new * qty
    total_old = price_old * qty
    buttons = []
    if price_new > 0:
        buttons.append([InlineKeyboardButton(
            text=f'Новый: {price_new:,} x {qty} = {total_new:,} тг',
            callback_data=f'price_ok:{price_new}'
        )])
    if price_old > 0 and price_old != price_new:
        buttons.append([InlineKeyboardButton(
            text=f'Старый: {price_old:,} x {qty} = {total_old:,} тг',
            callback_data=f'price_ok:{price_old}'
        )])
    buttons.append([InlineKeyboardButton(text='Ввести цену вручную', callback_data='price_manual')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
        [InlineKeyboardButton(text='Стандарт — 99 000 тг', callback_data='pkg:99000')],
        [InlineKeyboardButton(text='Стандарт+ — 199 000 тг', callback_data='pkg:199000')],
        [InlineKeyboardButton(text='Премиум — 599 000 тг', callback_data='pkg:599000')],
        [InlineKeyboardButton(text='Отмена', callback_data='cancel')],
    ])


def managers_kb() -> InlineKeyboardMarkup:
    from config import EMPLOYEES, LEADER
    all_mgrs = [LEADER] + [m for m in EMPLOYEES['managers'] if m != LEADER]
    rows = []
    for i in range(0, len(all_mgrs), 2):
        row = [InlineKeyboardButton(text=n, callback_data=f'mgr:{n}')
               for n in all_mgrs[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_date_kb() -> InlineKeyboardMarkup:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%d.%m.%Y")
    yesterday = (now - timedelta(days=1)).strftime("%d.%m.%Y")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Сегодня ({today})', callback_data=f'pdate:{today}')],
        [InlineKeyboardButton(text=f'Вчера ({yesterday})', callback_data=f'pdate:{yesterday}')],
        [InlineKeyboardButton(text='Выбрать из календаря', callback_data='pdate:cal')],
        [InlineKeyboardButton(text='Отмена', callback_data='cancel')],
    ])


DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
MONTHS_RU = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
             'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']


def calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_d = now.day if now.year == year and now.month == month else -1
    rows = []
    rows.append([
        InlineKeyboardButton(text='◀', callback_data=f'pdate:nav:{year}:{month}:-1'),
        InlineKeyboardButton(text=f'{MONTHS_RU[month]} {year}', callback_data='pdate:noop'),
        InlineKeyboardButton(text='▶', callback_data=f'pdate:nav:{year}:{month}:1'),
    ])
    rows.append([InlineKeyboardButton(text=d, callback_data='pdate:noop') for d in DAYS_RU])
    first_weekday, days_in_month = calendar.monthrange(year, month)
    day = 1
    for week in range(6):
        row = []
        for wd in range(7):
            if (week == 0 and wd < first_weekday) or day > days_in_month:
                row.append(InlineKeyboardButton(text=' ', callback_data='pdate:noop'))
            else:
                date_str = f'{day:02d}.{month:02d}.{year}'
                label = f'[{day}]' if day == today_d else str(day)
                row.append(InlineKeyboardButton(text=label, callback_data=f'pdate:day:{date_str}'))
                day += 1
        rows.append(row)
        if day > days_in_month:
            break
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
