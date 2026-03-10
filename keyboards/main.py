from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(role: str):
    buttons = []
    if role in ("menedzher", "rukovoditel", "manager", "accountant", "менеджер", "руководитель", "бухгалтер"):
        buttons.append([KeyboardButton(text="Vnesit oplatu")])
        buttons.append([KeyboardButton(text="Otchety")])
        buttons.append([KeyboardButton(text="Moy profil")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Otmena", callback_data="cancel")]])
