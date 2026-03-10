import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from services.sheets import get_report
from keyboards.reports import reports_kb
from services.users import get_user_info

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text == "Za segodnya")
@router.message(F.text == "Za nedelyu")
@router.message(F.text == "Za mesyats")
@router.message(F.text == "Po menedzheram")
@router.message(F.text == "Po kategoriyam")
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
    report_type = callback.data.split(":", 1)[1]
    await callback.message.edit_text("Zagruzhau otchet...")
    try:
        text = get_report(report_type, user)
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Report error: {e}")
        await callback.message.edit_text(f"Oshibka: {e}")
    await callback.answer()
