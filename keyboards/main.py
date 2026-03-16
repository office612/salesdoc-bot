from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(role: str) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text='💳 Внести оплату')]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='❌ Отмена', callback_data='cancel')
    ]])

