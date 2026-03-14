from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def reports_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За сегодня", callback_data="report:today"),
         InlineKeyboardButton(text="📆 За неделю", callback_data="report:week")],
        [InlineKeyboardButton(text="🗓 За месяц", callback_data="report:month")],
        [InlineKeyboardButton(text="👥 По менеджерам", callback_data="report:managers"),
         InlineKeyboardButton(text="📦 По категориям", callback_data="report:categories")],
        [InlineKeyboardButton(text="⚠️ Не посаженные", callback_data="report:unseated"),
         InlineKeyboardButton(text="✅ Посаженные", callback_data="report:seated")],
    ])


def back_to_reports_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к отчётам", callback_data="back:reports")]
    ])
