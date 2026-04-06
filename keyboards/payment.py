from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import calendar
import pytz

from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS, MONTH_SHEETS, PRICES_NEW, PRICES_OLD, TIMEZONE

TOP_CATEGORIES = ['new_client', 'nov_vnedrenie', 'nov_integr', 'abon_plata', 'oplata_dolga', 'balans']

# Календарь: названия дней и месяцев
DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
MONTHS_RU = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
             'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']


def back_button(callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="<< Назад", callback_data=callback_data)


def categories_kb(show_all: bool = False) -> InlineKeyboardMarkup:
    if show_all:
        buttons = [
            [InlineKeyboardButton(text=label, callback_data=f'cat:{key}')]
            for key, label in CATEGORIES
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text=label, callback_data=f'cat:{key}')]
            for key, label in CATEGORIES if key in TOP_CATEGORIES
        ]
        buttons.append([InlineKeyboardButton(text="Ещё ▼", callback_data="cat:show_all")])
    buttons.append([back_button("back:month")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def license_types_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=lt, callback_data=f'lic:{lt}')]
        for lt in LICENSE_TYPES
    ]
    buttons.append([back_button("back:category")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def periods_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=p, callback_data=f'per:{p}')]
        for p in PERIODS if p not in ("Баланс", "Услуга")
    ]
    buttons.append([back_button("back:qty")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_price_kb(new_price: int, old_price: int) -> InlineKeyboardMarkup:
    if new_price == old_price:
        buttons = [
            [InlineKeyboardButton(text=f"Подтвердить: {new_price:,} тг".replace(",", " "), callback_data=f"price:confirm:{new_price}")],
            [InlineKeyboardButton(text="Ввести вручную", callback_data="price:manual")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text=f"Новый клиент: {new_price:,} тг".replace(",", " "), callback_data=f"price:confirm:{new_price}")],
            [InlineKeyboardButton(text=f"Старый клиент: {old_price:,} тг".replace(",", " "), callback_data=f"price:confirm:{old_price}")],
            [InlineKeyboardButton(text="Ввести вручную", callback_data="price:manual")],
        ]
    buttons.append([back_button("back:period")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def banks_kb(back_to: str = "back:price") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=b, callback_data=f'bank:{b}')]
        for b in BANKS
    ]
    buttons.append([back_button(back_to)])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить", callback_data="confirm:yes")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def skip_receipt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить (без чека)", callback_data="skip_receipt")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def months_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f'month:{num}')]
        for num, name in MONTH_SHEETS.items()
    ]
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def package_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Пакет 1 (99 000)", callback_data="pkg:99000")],
        [InlineKeyboardButton(text="Пакет 2 (199 000)", callback_data="pkg:199000")],
        [InlineKeyboardButton(text="Пакет 3 (599 000)", callback_data="pkg:599000")],
    ]
    buttons.append([back_button("back:client")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_date_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора даты: Сегодня, Вчера, Календарь"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%d.%m.%Y")
    yesterday = (now - timedelta(days=1)).strftime("%d.%m.%Y")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Сегодня ({today})', callback_data=f'pdate:{now.date().isoformat()}')],
        [InlineKeyboardButton(text=f'Вчера ({yesterday})', callback_data=f'pdate:{(now - timedelta(days=1)).date().isoformat()}')],
        [InlineKeyboardButton(text='Выбрать из календаря', callback_data='pdate:cal')],
        [InlineKeyboardButton(text='Отмена', callback_data='cancel')],
    ])


def calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    """Мини-календарь для выбора даты"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_d = now.day if now.year == year and now.month == month else -1
    rows = []
    # Заголовок с навигацией
    rows.append([
        InlineKeyboardButton(text='◀', callback_data=f'pdate:nav:{year}:{month}:-1'),
        InlineKeyboardButton(text=f'{MONTHS_RU[month]} {year}', callback_data='pdate:noop'),
        InlineKeyboardButton(text='▶', callback_data=f'pdate:nav:{year}:{month}:1'),
    ])
    # Дни недели
    rows.append([InlineKeyboardButton(text=d, callback_data='pdate:noop') for d in DAYS_RU])
    # Дни месяца
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
            if day > days_in_month and wd == 6:
                break
        rows.append(row)
        if day > days_in_month:
            break
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def managers_kb() -> InlineKeyboardMarkup:
    """Клавиатура списка менеджеров (2 колонки)"""
    from config import EMPLOYEES, LEADER
    all_mgrs = [LEADER] + [m for m in EMPLOYEES.get('managers', []) if m != LEADER]
    rows = []
    for i in range(0, len(all_mgrs), 2):
        row = [InlineKeyboardButton(text=n, callback_data=f'mgr:{n}')
               for n in all_mgrs[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='Отмена', callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_month_kb() -> InlineKeyboardMarkup:
    return months_kb()


def activation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="activ:yes")],
        [InlineKeyboardButton(text="Нет", callback_data="activ:no")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def act_period_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=p, callback_data=f'actper:{p}')]
        for p in PERIODS if p not in ("Баланс", "Услуга")
    ]
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def bot_periods_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Месяц", callback_data="botper:Месяц")],
        [InlineKeyboardButton(text="3 месяца", callback_data="botper:3 месяца")],
        [InlineKeyboardButton(text="6 месяцев", callback_data="botper:6 месяцев")],
        [InlineKeyboardButton(text="12 месяцев", callback_data="botper:12 месяцев")],
    ]
    buttons.append([back_button("back:client")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def manual_amount_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [back_button("back:client")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def add_service_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, добавить услугу", callback_data="add_service:yes")],
        [InlineKeyboardButton(text="Нет, завершить", callback_data="add_service:no")],
    ])


def service_categories_kb() -> InlineKeyboardMarkup:
    service_cats = [
        ('nov_vnedrenie', 'Нов. внедрение'),
        ('nov_integr', 'Нов. интеграция'),
        ('sta_vnedrenie', 'Ста. внедрение'),
        ('sta_integr', 'Ста. интеграция'),
        ('nakladnaya', 'Накладная'),
        ('telegram_boty', 'Телеграм боты'),
        ('bot_otchet', 'Бот отчет'),
        ('bot_zakaz', 'Бот заказ'),
        ('dorabotka', 'Доработка'),
        ('dop_obuchenie', 'Доп. обучение'),
    ]
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f'svc:{key}')]
        for key, label in service_cats
    ]
    buttons.append([InlineKeyboardButton(text="Готово", callback_data="add_service:done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
