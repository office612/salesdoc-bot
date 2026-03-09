from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CATEGORIES, LICENSE_TYPES, PERIODS, BANKS

def categories_kb():
    rows = []
    for i in range(0, len(CATEGORIES), 2):
        row = [InlineKeyboardButton(text=cat[1], callback_data=f"cat:{cat[0]}") for cat in CATEGORIES[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def license_types_kb():
    rows = [[InlineKeyboardButton(text=t, callback_data=f"lt:{t}") for t in LICENSE_TYPES[i:i+3]] for i in range(0, len(LICENSE_TYPES), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def periods_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=p, callback_data=f"period:{p}") for p in PERIODS]])

def banks_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=b, callback_data=f"bank:{b}") for b in BANKS]])

def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅", callback_data="pay_confirm"), InlineKeyboardButton(text="❌", callback_data="cancel")]])

def skip_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭ Propustit'", callback_data="skip")]])

def amount_suggest_kb(suggested):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ {suggested}", callback_data=f"use_amount:{suggested}")], [InlineKeyboardButton(text="⌏", callback_data="enter_amount")]])

def seat_payment_kb(row_num, month):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Posadit", callback_data=f"seat:{row_num}:{month}")]])
