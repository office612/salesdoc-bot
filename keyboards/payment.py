from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import calendar
import pytz

from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS, MONTH_SHEETS, PRICES_NEW, PRICES_OLD, TIMEZONE

TOP_CATEGORIES = ['new_client', 'nov_vnedrenie', 'nov_integr', 'abon_plata', 'oplata_dolga', 'balans']


# ─────────────────────────────────────────────────────────────────────────────
# УТИЛИТА: единообразная кнопка «Назад»
# ─────────────────────────────────────────────────────────────────────────────
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
                                    [InlineKeyboardButton(text=f"Подтвердить: {new_price} тг", callback_data=f"price:confirm:{new_price}")],
                                    [InlineKeyboardButton(text="Ввести вручную", callback_data="price:manual")],
                    ]
else:
        buttons = [
                        [InlineKeyboardButton(text=f"Новый клиент: {new_price} тг", callback_data=f"price:confirm:{new_price}")],
                        [InlineKeyboardButton(text=f"Старый клиент: {old_price} тг", callback_data=f"price:confirm:{old_price}")],
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
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).date()
        buttons = []
        for i in range(7):
                    d = today - timedelta(days=i)
                    label = d.strftime("%d.%m.%Y")
                    if i == 0:
                                    label += " (сегодня)"
elif i == 1:
            label += " (вчера)"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"pdate:{d.isoformat()}")])
    buttons.append([InlineKeyboardButton(text="Другая дата...", callback_data="pdate:other")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


# ─────────────────────────────────────────────────────────────────────────────
# НОВЫЕ КЛАВИАТУРЫ
# ─────────────────────────────────────────────────────────────────────────────

def bot_periods_kb() -> InlineKeyboardMarkup:
        """Клавиатура периодов для ботов (только абон плата)."""
        periods = ["Месячный", "3 месячный", "6 месячный", "12 месяцев"]
        buttons = [
            [InlineKeyboardButton(text=p, callback_data=f'botper:{p}')]
            for p in periods
        ]
        buttons.append([back_button("back:client")])
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)


def manual_amount_kb() -> InlineKeyboardMarkup:
        """Клавиатура для ручного ввода суммы (только назад и отмена)."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [back_button("back:client")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
        ])


def add_service_kb() -> InlineKeyboardMarkup:
        """Спрашиваем: добавить услугу к новому клиенту?"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, добавить услугу", callback_data="add_service:yes")],
            [InlineKeyboardButton(text="Нет, завершить", callback_data="add_service:no")],
        ])


def service_categories_kb() -> InlineKeyboardMarkup:
        """Список услуг для добавления к новому клиенту."""
        services = [
            ("nov_vnedrenie", "Нов внедрение"),
            ("nov_integr", "Нов интеграция"),
            ("telegram_boty", "телеграм боты"),
            ("bot_otchet", "Бот отчет"),
            ("bot_zakaz", "Бот заказ"),
            ("dorabotka", "доработка"),
            ("dop_obuchenie", "доп обучение"),
            ("dvagis", "2гис"),
        ]
        buttons = [
            [InlineKeyboardButton(text=label, callback_data=f'svc:{key}')]
            for key, label in services
        ]
        buttons.append([InlineKeyboardButton(text="Готово, завершить", callback_data="add_service:done")])
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
