from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(role: str) -> ReplyKeyboardMarkup:
    buttons = []
    if role in ("menedzher", "rukovoditel"):
        buttons.append([KeyboardButton(text="💳 Vnesit oplatu")])
    if role in ("menedzher", "rukovoditel", "buhgalter"):
        buttons.append([
            KeyboardButton(text="📊 Otchety"),
            KeyboardButton(text="👤 Moy profil"),
        ])
    if role in ("buhgalter", "rukovoditel"):
        buttons.append([KeyboardButton(text="⚠️ Ne posazhenye")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="❌ Otmena", callback_data="cancel")
        ]]
    )
