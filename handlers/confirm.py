import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.sheets import mark_planted
from services.users import get_user_info, is_accountant, is_leader

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("planted:"))
async def planted_payment(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user or not (is_accountant(user) or is_leader(user)):
        await callback.answer("Только бухгалтер или руководитель.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверные данные", show_alert=True)
        return
    row_num = int(parts[1])
    month = int(parts[2])
    ok = mark_planted(row_num, month)
    if ok:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>ПОСАЖЕНО</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Ошибка при посадке.",
            parse_mode="HTML"
        )
    await callback.answer()
