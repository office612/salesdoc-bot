from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MONTHS = [
    (1, 'Янв'), (2, 'Фев'), (3, 'Мар'), (4, 'Апр'),
    (5, 'Май'), (6, 'Июн'), (7, 'Июл'), (8, 'Авг'),
    (9, 'Сен'), (10, 'Окт'), (11, 'Ноя'), (12, 'Дек'),
]

def reports_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📅 За сегодня', callback_data='report:today'),
         InlineKeyboardButton(text='📆 За неделю', callback_data='report:week')],
        [InlineKeyboardButton(text='🗓 Выбрать месяц', callback_data='report:pick_month')],
        [InlineKeyboardButton(text='👥 По менеджерам', callback_data='report:managers'),
         InlineKeyboardButton(text='📦 По категориям', callback_data='report:categories')],
        [InlineKeyboardButton(text='⚠️ Не посаженные', callback_data='report:unseated'),
         InlineKeyboardButton(text='✅ Посаженные', callback_data='report:seated')],
    ])


def months_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, 12, 3):
        row = [InlineKeyboardButton(text=MONTHS[j][1], callback_data=f'report:month:{MONTHS[j][0]}')
               for j in range(i, min(i+3, 12))]
        rows.append(row)
    rows.append([InlineKeyboardButton(text='◀️ Назад', callback_data='back:reports')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_reports_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='◀️ Назад к отчётам', callback_data='back:reports')]
    ])
