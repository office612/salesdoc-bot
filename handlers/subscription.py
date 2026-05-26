"""Подписка/отписка на уведомления @SDfinansbot.

Поток отписки:
1. Юзер нажимает «🔕 Отписаться» под уведомлением → callback unsub:start
2. Бот показывает подтверждение → callback unsub:yes / unsub:no
3. На yes: запись в users.subscribed=FALSE + личное уведомление директору
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command

from services.sheets import set_subscription, get_user_name
from config import DIRECTOR_ID

logger = logging.getLogger(__name__)
router = Router()


def confirm_unsub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, отписаться", callback_data="unsub:yes"),
            InlineKeyboardButton(text="Отмена", callback_data="unsub:no"),
        ]
    ])


@router.callback_query(F.data == "unsub:start")
async def unsub_start(callback: CallbackQuery):
    """Шаг 1: показать подтверждение."""
    await callback.message.answer(
        "Точно отписаться от уведомлений об оплатах?\n"
        "Можно будет вернуться через /subscribe",
        reply_markup=confirm_unsub_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "unsub:no")
async def unsub_cancel(callback: CallbackQuery):
    """Шаг 2: отмена."""
    try:
        await callback.message.edit_text(
            "Отписка отменена. Уведомления продолжат приходить."
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "unsub:yes")
async def unsub_confirm(callback: CallbackQuery):
    """Шаг 3: подтверждение — записываем в Sheets и уведомляем директора."""
    uid = callback.from_user.id
    ok = set_subscription(uid, subscribed=False)
    if not ok:
        await callback.answer("Не получилось отписать, напиши директору", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            "Отписан. Больше уведомления не приходят.\n"
            "Если передумаешь — отправь /subscribe"
        )
    except Exception:
        pass

    # Уведомление директору о том что юзер отписался
    try:
        name = get_user_name(uid) or callback.from_user.full_name
        username = f"@{callback.from_user.username}" if callback.from_user.username else "—"
        await callback.bot.send_message(
            DIRECTOR_ID,
            f"ℹ️ <b>{name}</b> ({username}) отписался от уведомлений об оплатах.\n\n"
            f"Если это ошибка — пусть напишет /subscribe боту."
        )
    except Exception as e:
        logger.warning(f"notify director about unsub failed: {e}")

    await callback.answer("Готово")


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    """Подписаться обратно."""
    uid = message.from_user.id
    ok = set_subscription(uid, subscribed=True)
    if ok:
        await message.answer("Подписка восстановлена. Уведомления снова будут приходить.")
        # Уведомляем директора
        try:
            name = get_user_name(uid) or message.from_user.full_name
            username = f"@{message.from_user.username}" if message.from_user.username else "—"
            await message.bot.send_message(
                DIRECTOR_ID,
                f"ℹ️ <b>{name}</b> ({username}) снова подписался на уведомления."
            )
        except Exception:
            pass
    else:
        await message.answer(
            "Не получилось восстановить подписку — возможно тебя нет в таблице users. "
            "Напиши директору."
        )


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    """Альтернатива кнопке: отписка командой."""
    await message.answer(
        "Точно отписаться от уведомлений об оплатах?\n"
        "Можно будет вернуться через /subscribe",
        reply_markup=confirm_unsub_kb()
    )
