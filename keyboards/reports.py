from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def reports_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За сегодня", callback_data="report:today")],
        [InlineKeyboardButton(text="📆 Лент з за неделю д недель", callback_data="report:week")],
        [InlineKeyboardButton(text="🗓 Месяц", callback_data="report:month")],
        [InlineKeyboardButton(text="👤 Незакрышенные", callback_data="report:managers")],
        [InlineKeyboardButton(text="📋 �Статьям", callback_data="report:categories")],
        [InlineKeyboardButton(text="💺 Ne posadhenye", callback_data="report:unseated")],
        [InlineKeyboardButton(text="✅ Posadhenye", callback_data="report:seated")],
    ])
