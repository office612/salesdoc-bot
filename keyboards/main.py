from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(role: str):
    buttons = []
    if role in ("menedzher", "rukovoditel"):
        buttons.append([KeyboardButton(text="💳 Внести оплату")])
    buttons.append([KeyboardButton(text="📊 Отчёты")])
    buttons.append([KeyboardButton(text="💺")])
    buttons.append([KeyboardButton(text="👤 Мой профиль")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⍌ Отмена", callback_data="cancel")]])
