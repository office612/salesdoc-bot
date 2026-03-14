from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(role: str) -> ReplyKeyboardMarkup:
    buttons = []
    if role in ("menedzher", "rukovoditel"):
        buttons.append([KeyboardButton(text="💳 Внести оплату")])
    if role in ("menedzher", "rukovoditel", "buhgalter"):
        buttons.append([
            KeyboardButton(text="📊 Отчёты"),
            KeyboardButton(text="👤 Мой профиль"),
        ])
    if role in ("buhgalter", "rukovoditel"):
        buttons.append([KeyboardButton(text="⚠️ Не посаженные")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ]]
    )
