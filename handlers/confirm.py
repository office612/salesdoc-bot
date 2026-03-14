import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.sheets import confirm_payment
from services.users import get_user_info, is_accountant, is_leader

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("seat:"))
async def seat_payment(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user or not (is_accountant(user) or is_leader(user)):
        await callback.answer("Tolko buhgalter ili rukovoditel.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Nevernye dannye", show_alert=True)
        return
    row_num = int(parts[1])
    month = int(parts[2])
    ok = confirm_payment(row_num, month)
    if ok:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>POSAZHEN</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Oshibka pri posadke",
            parse_mode="HTML"
        )
    await callback.answer()
