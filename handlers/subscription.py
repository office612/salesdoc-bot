"""Подписка/отписка на уведомления @SDfinansbot + защита от чужих.

Поток отписки:
1. Юзер нажимает «🔕 Отписаться» под уведомлением → callback unsub:start
2. Бот показывает подтверждение → callback unsub:yes / unsub:no
3. На yes: запись в users.subscribed=FALSE + личное уведомление директору

Доступ — только тем, кто в users sheet или в ACCOUNTANT_IDS.
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command, CommandStart

from services.sheets import set_subscription, get_user_name, get_user
from config import DIRECTOR_ID, ACCOUNTANT_IDS

logger = logging.getLogger(__name__)
router = Router()


def _has_access(uid: int) -> bool:
    """Доступ к боту: директор, бухгалтеры из env, или зарегистрированные в users."""
    if uid == DIRECTOR_ID:
        return True
    if uid in ACCOUNTANT_IDS:
        return True
    if get_user(uid):
        return True
    return False


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
    if not _has_access(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    await callback.message.answer(
        "Точно отписаться от уведомлений об оплатах?\n"
        "Можно будет вернуться через /subscribe",
        reply_markup=confirm_unsub_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "unsub:no")
async def unsub_cancel(callback: CallbackQuery):
    """Шаг 2: отмена."""
    if not _has_access(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
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
    if not _has_access(uid):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
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
    if not _has_access(uid):
        await message.answer("🚫 Это служебный бот, у тебя нет доступа.")
        return
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
    if not _has_access(message.from_user.id):
        await message.answer("🚫 Это служебный бот, у тебя нет доступа.")
        return
    await message.answer(
        "Точно отписаться от уведомлений об оплатах?\n"
        "Можно будет вернуться через /subscribe",
        reply_markup=confirm_unsub_kb()
    )


@router.message(CommandStart())
async def cmd_start_kassa(message: Message):
    """Любой /start у @SDfinansbot. Для своих — приветствие, для чужих — отказ."""
    uid = message.from_user.id
    if not _has_access(uid):
        await message.answer(
            "🚫 Это служебный бот SalesDoc.\n"
            "У тебя нет доступа."
        )
        # Сообщаем директору о попытке доступа — чтоб видеть кто пытался
        try:
            tg = message.from_user
            username = f"@{tg.username}" if tg.username else "нет username"
            await message.bot.send_message(
                DIRECTOR_ID,
                f"⚠️ Попытка доступа к @SDfinansbot\n"
                f"👤 {tg.full_name} | {username}\n"
                f"🆔 <code>{tg.id}</code>"
            )
        except Exception:
            pass
        return

    name = get_user_name(uid) or "—"
    await message.answer(
        f"<b>{name}</b>, ты подключен к уведомлениям об оплатах.\n\n"
        f"Что приходит сюда: новые оплаты от операторов с кнопкой «Посажено».\n\n"
        f"Команды:\n"
        f"• /subscribe — включить уведомления\n"
        f"• /unsubscribe — отключить уведомления"
    )


@router.message()
async def fallback_unknown(message: Message):
    """Любое сообщение от не-своих — отказ. Защищает от случайных диалогов."""
    if not _has_access(message.from_user.id):
        await message.answer("🚫 Это служебный бот, у тебя нет доступа.")
        return
    # Для своих — мягкая подсказка
    await message.answer(
        "Я не понял команду. Доступно:\n"
        "• /subscribe — включить уведомления\n"
        "• /unsubscribe — отключить уведомления"
    )
