"""Хендлеры ЗВС-бота для сотрудников (@finzvsbot).

Сотрудник:
- /start → приветствие или запрос доступа (директору летит в его отдельный бот)
- /zayavka → FSM заполнения (сумма → на что → счёт → подтверждение)
- /history → последние свои заявки
- /cancel → отмена текущего ввода

Уведомления директору шлются через @SDzvsdirector (отдельный бот). Все
кнопки одобрения и их callbacks обрабатывает handlers/zvs_director.py.
"""

import logging
import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from states.zvs import ZvsApply
from keyboards.zvs import (
    zvs_main_menu, confirm_apply_kb, accounts_kb,
    director_decision_kb, director_approve_kb,
)
from config import BANKS, DIRECTOR_ID
from services.sheets import get_user
from services.zvs_sheets import create_request, get_user_requests
from services.zvs_pending import add as pending_add

logger = logging.getLogger(__name__)
router = Router()


def _is_registered(uid: int) -> bool:
    return uid == DIRECTOR_ID or get_user(uid) is not None


def _format_amount(amount) -> str:
    """50000 → '50 000'."""
    try:
        n = int(str(amount).replace(" ", "").replace(",", ""))
        return f"{n:,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


async def _open_director_bot() -> Bot:
    """Создать клиент к директорскому боту (для отправки ему уведомлений)."""
    token = os.getenv("ZVS_DIR_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("ZVS_DIR_BOT_TOKEN не задан — некуда слать заявки")
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


# ────────────────────────────────────────────────────────────
# /start — регистрация
# ────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id

    if _is_registered(uid):
        user = get_user(uid) or {}
        name = user.get("name") or message.from_user.full_name
        await message.answer(
            f"<b>{name}</b>, бот ЗВС готов к работе.\n\n"
            f"Нажми «💸 Подать заявку» когда нужны деньги.",
            reply_markup=zvs_main_menu()
        )
        return

    # Новый юзер — отправляем запрос директору в его отдельный бот
    tg = message.from_user
    name = tg.full_name
    username = f"@{tg.username}" if tg.username else "—"

    pending_add(uid, name, tg.username or "")

    await message.answer(
        "🚫 У тебя нет доступа к ЗВС-боту.\n\n"
        "Запрос отправлен директору. Дождись одобрения и нажми /start ещё раз."
    )

    director_bot = None
    try:
        director_bot = await _open_director_bot()
        await director_bot.send_message(
            DIRECTOR_ID,
            f"🔔 <b>Запрос доступа к ЗВС-боту</b>\n\n"
            f"👤 {name}\n"
            f"Username: {username}\n"
            f"🆔 <code>{uid}</code>",
            reply_markup=director_approve_kb(uid)
        )
    except Exception as e:
        logger.warning(f"notify director on register: {e}")
    finally:
        if director_bot:
            await director_bot.session.close()


# ────────────────────────────────────────────────────────────
# Подача заявки — FSM
# ────────────────────────────────────────────────────────────

@router.message(Command("zayavka"))
@router.message(F.text == "💸 Подать заявку")
async def start_apply(message: Message, state: FSMContext):
    if not _is_registered(message.from_user.id):
        await message.answer("🚫 Нет доступа. Сначала /start")
        return
    await state.clear()
    await state.set_state(ZvsApply.waiting_amount)
    await message.answer(
        "💰 На какую сумму? (число в тенге)\n\n"
        "Например: <code>50000</code>\n\n"
        "Чтоб отменить — /cancel"
    )


@router.message(Command("cancel"))
async def cancel_apply(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("Отменено.", reply_markup=zvs_main_menu())
    else:
        await message.answer("Нечего отменять.")


@router.message(ZvsApply.waiting_amount)
async def step_amount(message: Message, state: FSMContext):
    raw = (message.text or "").replace(" ", "").replace(",", "")
    try:
        amount = int(raw)
    except ValueError:
        await message.answer(
            "Не понял сумму. Введи число без букв.\n"
            "Например: <code>50000</code>"
        )
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    if amount > 100_000_000:
        await message.answer("Сумма слишком большая. Проверь нолики.")
        return

    await state.update_data(amount=amount)
    await state.set_state(ZvsApply.waiting_purpose)
    await message.answer(
        f"📝 На что нужны {_format_amount(amount)} тг?\n\n"
        f"Опиши коротко (например: «Ремонт принтера в офисе»)"
    )


@router.message(ZvsApply.waiting_purpose)
async def step_purpose(message: Message, state: FSMContext):
    purpose = (message.text or "").strip()
    if len(purpose) < 3:
        await message.answer("Слишком коротко. Опиши хотя бы парой слов.")
        return
    if len(purpose) > 500:
        await message.answer("Слишком длинно. Сократи до 500 символов.")
        return

    await state.update_data(purpose=purpose)
    await state.set_state(ZvsApply.waiting_account)
    await message.answer(
        "🏦 С какого счёта снять?",
        reply_markup=accounts_kb()
    )


@router.callback_query(F.data.startswith("zvs_acc:"), ZvsApply.waiting_account)
async def step_account(callback: CallbackQuery, state: FSMContext):
    account = callback.data.split(":", 1)[1]
    if account not in BANKS:
        await callback.answer("Битый счёт", show_alert=True)
        return

    await state.update_data(account=account)
    data = await state.get_data()
    await state.set_state(ZvsApply.waiting_confirm)

    text = (
        f"Проверь заявку:\n\n"
        f"💰 <b>{_format_amount(data['amount'])} тг</b>\n"
        f"📝 {data['purpose']}\n"
        f"🏦 {account.capitalize()}\n\n"
        f"Отправить директору?"
    )
    try:
        await callback.message.edit_text(text, reply_markup=confirm_apply_kb())
    except Exception:
        await callback.message.answer(text, reply_markup=confirm_apply_kb())
    await callback.answer()


@router.callback_query(F.data == "zvs_apply:cancel", ZvsApply.waiting_confirm)
async def confirm_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("Отменено. Заявка не отправлена.")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "zvs_apply:send", ZvsApply.waiting_confirm)
async def confirm_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    purpose = data.get("purpose", "")
    account = data.get("account", "")
    uid = callback.from_user.id

    user = get_user(uid) or {}
    name = user.get("name") or callback.from_user.full_name

    zvs_id = create_request(uid, name, amount, purpose, account)
    if not zvs_id:
        await callback.message.edit_text(
            "❌ Не получилось создать заявку (проблема с таблицей). "
            "Попробуй ещё раз чуть позже или напиши директору."
        )
        await callback.answer()
        await state.clear()
        return

    # Подтверждение заявителю
    try:
        await callback.message.edit_text(
            f"✅ Заявка №{zvs_id} отправлена директору.\n\n"
            f"💰 {_format_amount(amount)} тг\n"
            f"📝 {purpose}\n"
            f"🏦 {account.capitalize()}\n\n"
            f"Жди решение — придёт сюда."
        )
    except Exception:
        pass

    # Уведомление директору — через ОТДЕЛЬНЫЙ директорский бот
    username = f"@{callback.from_user.username}" if callback.from_user.username else "—"
    director_bot = None
    try:
        director_bot = await _open_director_bot()
        await director_bot.send_message(
            DIRECTOR_ID,
            f"💸 <b>Новая ЗВС №{zvs_id}</b>\n\n"
            f"👤 {name} ({username})\n"
            f"💰 <b>{_format_amount(amount)} тг</b>\n"
            f"📝 {purpose}\n"
            f"🏦 {account.capitalize()}",
            reply_markup=director_decision_kb(zvs_id, uid)
        )
    except Exception as e:
        logger.error(f"notify director about new zvs: {e}")
    finally:
        if director_bot:
            await director_bot.session.close()

    await callback.answer("Отправлено")
    await state.clear()


# ────────────────────────────────────────────────────────────
# /history — мои заявки
# ────────────────────────────────────────────────────────────

@router.message(Command("history"))
@router.message(F.text == "📋 Мои заявки")
async def my_history(message: Message):
    uid = message.from_user.id
    if not _is_registered(uid):
        await message.answer("🚫 Нет доступа. Сначала /start")
        return
    reqs = get_user_requests(uid, limit=10)
    if not reqs:
        await message.answer("У тебя пока нет заявок.")
        return
    lines = ["📋 <b>Твои последние заявки:</b>\n"]
    for r in reqs:
        status = r.get("status", "—")
        emoji = "⏳"
        if status == "Одобрено":
            emoji = "✅"
        elif status == "Отклонено":
            emoji = "❌"
        elif status == "На доработку":
            emoji = "🔄"
        amount = _format_amount(r.get("amount", "—"))
        purpose = (r.get("purpose", "") or "")[:60]
        acc = (r.get("account", "") or "—").capitalize()
        lines.append(
            f"{emoji} №{r.get('id', '?')} · {amount} тг · {acc}\n"
            f"  {purpose}\n"
            f"  {r.get('created_at', '')} · {status}"
        )
    await message.answer("\n\n".join(lines))


# ────────────────────────────────────────────────────────────
# Fallback
# ────────────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        return
    if not _is_registered(message.from_user.id):
        await message.answer("🚫 Нет доступа. /start")
        return
    await message.answer(
        "Не понял. Команды:\n"
        "• /zayavka — подать заявку\n"
        "• /history — мои заявки\n"
        "• /cancel — отменить текущий ввод"
    )
