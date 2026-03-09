from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def reports_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Za segodnya", callback_data="report:today")],
        [InlineKeyboardButton(text="Za nedelyu", callback_data="report:week")],
        [InlineKeyboardButton(text="Za mesyats", callback_data="report:month")],
        [InlineKeyboardButton(text="Po menedzheram", callback_data="report:managers")],
        [InlineKeyboardButton(text="Po kategoriyam", callback_data="report:categories")],
        [InlineKeyboardButton(text="Ne posazhenye", callback_data="report:unseated")],
        [InlineKeyboardButton(text="Posazhenye", callback_data="report:seated")],
    ])
