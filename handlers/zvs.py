"""Хендлеры ЗВС-бота (@SDzvsbot или как назовём).

Регистрация:
- /start → если юзер уже в users — приветствие и меню
- если нет — отправка запроса директору с кнопкой [Дать доступ]/[Отказать]

Заявка (FSM ZvsApply):
- /zayavka или кнопка «Подать заявку» → шаг сумма → шаг назначение → подтверждение → отправка
- Уведомление директора с кнопками [Одобрить][Отклонить][Доработка]

Решение директора (FSM ZvsDecision):
- На «Отклонить»/«Доработка» бот просит причину следующим сообщением.
- На «Одобрить» — сразу применяем.
- В обоих случаях заявителю прилетает уведомление.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from states.zvs import ZvsApply, ZvsDecision
from keyboards.zvs import (
    zvs_main_menu, confirm_apply_kb, accounts_kb,
    director_decision_kb, director_approve_kb,
)
from config import BANKS, DIRECTOR_ID
from services.sheets import get_user, register_user
from services.zvs_sheets import (
    create_request, get_request, update_decision, get_user_requests,
)
from services.zvs_pending import add as pending_add, get as pending_get, remove as pending_remove

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
        if uid == DIRECTOR_ID:
            await message.answer(
                f"<b>{name}</b>, ты директор.\n\n"
                f"Сюда будут приходить заявки от сотрудников.\n"
                f"Жми кнопки под уведомлением чтобы одобрить/отклонить."
            )
        else:
            await message.answer(
                f"<b>{name}</b>, бот ЗВС готов к работе.\n\n"
                f"Нажми «💸 Подать заявку» когда нужны деньги.",
                reply_markup=zvs_main_menu()
            )
        return

    # Новый юзер — отправляем запрос директору
    tg = message.from_user
    name = tg.full_name
    username = f"@{tg.username}" if tg.username else "—"

    pending_add(uid, name, tg.username or "")

    await message.answer(
        "🚫 У тебя нет доступа к ЗВС-боту.\n\n"
        "Запрос отправлен директору. Дождись одобрения и нажми /start ещё раз."
    )

    try:
        await message.bot.send_message(
            DIRECTOR_ID,
            f"🔔 <b>Запрос доступа к ЗВС-боту</b>\n\n"
            f"👤 {name}\n"
            f"Username: {username}\n"
            f"🆔 <code>{uid}</code>",
            reply_markup=director_approve_kb(uid)
        )
    except Exception as e:
        logger.warning(f"notify director on register: {e}")


@router.callback_query(F.data.startswith("zvs_reg:"))
async def handle_register(callback: CallbackQuery):
    if callback.from_user.id != DIRECTOR_ID:
        await callback.answer("Только директор может одобрять.", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Битые данные", show_alert=True)
        return
    _, action, tg_id_str = parts
    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await callback.answer("Битый ID", show_alert=True)
        return

    pending = pending_get(tg_id) or {}
    name = pending.get("name") or "Сотрудник"

    if action == "ok":
        register_user(tg_id, name, "employee")
        pending_remove(tg_id)
        try:
            await callback.message.edit_text(
                callback.message.text + f"\n\n✅ <b>Доступ открыт</b>"
            )
        except Exception:
            pass
        try:
            await callback.bot.send_message(
                tg_id,
                f"✅ Доступ к ЗВС-боту открыт!\n\n"
                f"Нажми /start чтобы начать."
            )
        except Exception as e:
            logger.warning(f"notify employee approved: {e}")
        await callback.answer("Готово")
    else:
        pending_remove(tg_id)
        try:
            await callback.message.edit_text(
                callback.message.text + f"\n\n❌ <b>Отказано</b>"
            )
        except Exception:
            pass
        try:
            await callback.bot.send_message(
                tg_id,
                "❌ В доступе отказано. Если ошибка — пиши директору лично."
            )
        except Exception:
            pass
        await callback.answer("Отказано")


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

    try:
        await callback.message.edit_text(
            f"Проверь заявку:\n\n"
            f"💰 <b>{_format_amount(data['amount'])} тг</b>\n"
            f"📝 {data['purpose']}\n"
            f"🏦 {account.capitalize()}\n\n"
            f"Отправить директору?",
            reply_markup=confirm_apply_kb()
        )
    except Exception:
        await callback.message.answer(
            f"Проверь заявку:\n\n"
            f"💰 <b>{_format_amount(data['amount'])} тг</b>\n"
            f"📝 {data['purpose']}\n"
            f"🏦 {account.capitalize()}\n\n"
            f"Отправить директору?",
            reply_markup=confirm_apply_kb()
        )
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

    # Уведомление директору
    username = f"@{callback.from_user.username}" if callback.from_user.username else "—"
    try:
        await callback.bot.send_message(
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

    await callback.answer("Отправлено")
    await state.clear()


# ────────────────────────────────────────────────────────────
# Кнопки директора
# ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("zvs_dec:"))
async def director_decision(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != DIRECTOR_ID:
        await callback.answer("Только директор", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Битые данные", show_alert=True)
        return
    _, action, zvs_id_str, applicant_uid_str = parts
    try:
        zvs_id = int(zvs_id_str)
        applicant_uid = int(applicant_uid_str)
    except ValueError:
        await callback.answer("Битые данные", show_alert=True)
        return

    req = get_request(zvs_id)
    if not req:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    # Если уже решено — показать алертом и не давать менять
    if req.get("status") and req["status"] != "Ожидает":
        await callback.answer(
            f"Уже {req['status'].lower()} ({req.get('decided_at', '')})",
            show_alert=True
        )
        return

    if action == "ap":
        ok = update_decision(zvs_id, "Одобрено")
        if not ok:
            await callback.answer("Не удалось записать в Sheets", show_alert=True)
            return
        await _finalize_decision(callback, zvs_id, applicant_uid, "Одобрено", req, "")
        return

    # Отклонить или Доработка — спрашиваем причину
    await state.update_data(
        zvs_id=zvs_id,
        applicant_uid=applicant_uid,
        original_message_id=callback.message.message_id,
    )
    if action == "rj":
        await state.set_state(ZvsDecision.waiting_reject_reason)
        await callback.message.answer(
            f"❌ Отклоняем ЗВС №{zvs_id}.\n\n"
            f"Напиши причину одним сообщением (заявитель её увидит).\n"
            f"Чтоб не отклонять — /cancel"
        )
    else:  # rw
        await state.set_state(ZvsDecision.waiting_rework_comment)
        await callback.message.answer(
            f"🔄 Возвращаем ЗВС №{zvs_id} на доработку.\n\n"
            f"Напиши что поправить (заявитель увидит).\n"
            f"Чтоб не возвращать — /cancel"
        )
    await callback.answer()


@router.message(ZvsDecision.waiting_reject_reason)
async def reject_reason(message: Message, state: FSMContext):
    if message.from_user.id != DIRECTOR_ID:
        return
    text = (message.text or "").strip()
    if text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отклонение отменено. Заявка остаётся в очереди.")
        return
    if len(text) < 3:
        await message.answer("Слишком коротко. Напиши понятнее.")
        return

    data = await state.get_data()
    zvs_id = data.get("zvs_id")
    applicant_uid = data.get("applicant_uid")
    ok = update_decision(zvs_id, "Отклонено", text)
    if not ok:
        await message.answer("❌ Не удалось записать. Попробуй позже.")
        await state.clear()
        return
    req = get_request(zvs_id) or {}
    await _finalize_decision(message, zvs_id, applicant_uid, "Отклонено", req, text)
    await state.clear()


@router.message(ZvsDecision.waiting_rework_comment)
async def rework_comment(message: Message, state: FSMContext):
    if message.from_user.id != DIRECTOR_ID:
        return
    text = (message.text or "").strip()
    if text.startswith("/cancel"):
        await state.clear()
        await message.answer("Доработка отменена. Заявка остаётся в очереди.")
        return
    if len(text) < 3:
        await message.answer("Слишком коротко. Напиши понятнее.")
        return

    data = await state.get_data()
    zvs_id = data.get("zvs_id")
    applicant_uid = data.get("applicant_uid")
    ok = update_decision(zvs_id, "На доработку", text)
    if not ok:
        await message.answer("❌ Не удалось записать. Попробуй позже.")
        await state.clear()
        return
    req = get_request(zvs_id) or {}
    await _finalize_decision(message, zvs_id, applicant_uid, "На доработку", req, text)
    await state.clear()


async def _finalize_decision(
    event,
    zvs_id: int,
    applicant_uid: int,
    status: str,
    req: dict,
    comment: str,
):
    """Уведомить директора (в т.ч. отредактировать оригинал) и заявителя."""
    emoji = "✅" if status == "Одобрено" else ("❌" if status == "Отклонено" else "🔄")
    amount = _format_amount(req.get("amount", "—"))
    purpose = req.get("purpose", "—")
    name = req.get("name", "—")
    account = req.get("account", "") or "—"

    tail = ""
    if comment:
        tail = f"\n💬 {comment}"

    director_text = (
        f"{emoji} <b>{status.upper()}</b>\n\n"
        f"ЗВС №{zvs_id}\n"
        f"👤 {name}\n"
        f"💰 {amount} тг\n"
        f"📝 {purpose}\n"
        f"🏦 {account.capitalize()}"
        f"{tail}"
    )

    # event — это либо CallbackQuery (одобрение в одно нажатие), либо Message (после ввода причины)
    bot = event.bot
    if hasattr(event, "message"):
        # CallbackQuery — редактируем оригинал
        try:
            await event.message.edit_text(director_text, reply_markup=None)
        except Exception:
            try:
                await bot.send_message(DIRECTOR_ID, director_text)
            except Exception:
                pass
    else:
        # Message (после ввода причины) — шлём новое сообщение
        try:
            await bot.send_message(DIRECTOR_ID, director_text)
        except Exception:
            pass

    # Уведомление заявителю
    applicant_text = (
        f"{emoji} <b>Заявка №{zvs_id} — {status.lower()}</b>\n\n"
        f"💰 {amount} тг\n"
        f"📝 {purpose}\n"
        f"🏦 {account.capitalize()}"
        f"{tail}"
    )
    try:
        await bot.send_message(applicant_uid, applicant_text)
    except Exception as e:
        logger.error(f"notify applicant {applicant_uid}: {e}")


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
# Fallback — любое непонятое сообщение
# ────────────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        # Если идёт FSM — это сообщение в нём
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
