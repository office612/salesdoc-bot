from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS


def categories_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(CATEGORIES), 2):
        row = [InlineKeyboardButton(text=cat[1], callback_data=f"cat:{cat[0]}") for cat in CATEGORIES[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Otmena", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def license_types_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(LICENSE_TYPES), 3):
        row = [InlineKeyboardButton(text=t, callback_data=f"lt:{t}") for t in LICENSE_TYPES[i:i+3]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Otmena", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def periods_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=p, callback_data=f"period:{p}") for p in PERIODS[:2]]]
    if len(PERIODS) > 2:
        rows.append([InlineKeyboardButton(text=p, callback_data=f"period:{p}") for p in PERIODS[2:]])
    rows.append([InlineKeyboardButton(text="❌ Otmena", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def banks_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=b, callback_data=f"bank:{b}") for b in BANKS[:3]]]
    if len(BANKS) > 3:
        rows.append([InlineKeyboardButton(text=b, callback_data=f"bank:{b}") for b in BANKS[3:]])
    rows.append([InlineKeyboardButton(text="❌ Otmena", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Podtverdit", callback_data="pay_confirm"),
            InlineKeyboardButton(text="❌ Otmena", callback_data="cancel"),
        ]
    ])


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭ Propustit", callback_data="skip")]])


def seat_payment_kb(row_num: int, month: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Posadit", callback_data=f"seat:{row_num}:{month}")]
    ])
