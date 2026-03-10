import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from services.sheets import get_payments_for_period
from keyboards.reports import reports_kb
from services.users import get_user_info

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text.in_({"Za segodnya", "Za nedelyu", "Za mesyats", "Po menedzheram", "Po kategoriyam"}))
async def open_reports_menu(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    await message.answer("Vyberte tip otcheta:", reply_markup=reports_kb())

@router.callback_query(F.data.startswith("report:"))
async def handle_report(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan", show_alert=True)
        return
    period = callback.data.split(":", 1)[1]
    today = date.today()
    if period == "today":
        start, end = today, today
    elif period == "week":
        start = today - timedelta(days=7)
        end = today
    elif period == "month":
        start = today.replace(day=1)
        end = today
    else:
        start, end = today.replace(day=1), today

    rows = get_payments_for_period(start, end)
    if not rows:
        await callback.message.answer("Dannyh net za etot period.")
        await callback.answer()
        return

    lines = []
    for r in rows[:20]:
        lines.append(f"{r.get('date','')} | {r.get('manager','')} | {r.get('amount','')} | {r.get('category','')}")
    text = "\n".join(lines)
    await callback.message.answer(f"Otchet:\n{text}")
    await callback.answer()
