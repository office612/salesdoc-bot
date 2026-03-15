from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS


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


def banks_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(BANKS), 2):
        row = [InlineKeyboardButton(text=BANKS[j], callback_data=f'bank:{BANKS[j]}')
               for j in range(i, min(i+2, len(BANKS)))]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Подтвердить', callback_data='pay_confirm')],
        [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')],
    ])


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⏭ Пропустить', callback_data='skip')],
        [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')],
    ])
