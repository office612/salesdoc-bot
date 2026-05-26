"""Хендлеры ЗВС-бота для сотрудников (@finzvsbot).

Сотрудник:
- /start → приветствие или запрос доступа (директору летит в его отдельный бот)
- /zayavka → FSM заполнения (сумма → на что → счёт → подтверждение)
- /history → последние свои заявки
- /cancel → отмена текущего ввода

Уведомления директору шлются через @SDzvsdirector (отдельный бот). Все
кнопки одобрения и их callbacks обрабатывает handlers/zvs_director.py.
"""

import json
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
from services.zvs_messages import save as save_applicant_msg

logger = logging.getLogger(__name__)
router = Router()


def _is_registered(uid: int) -> bool:
    return uid == DIRECTOR_ID or get_user(uid) is not None


def _format_amount(amount) -> str:
    """50000 → '50 000'. Робастно: парсит число даже если в строке есть «тг»,
    пробелы, запятые — иначе при чтении из Sheets (которые форматируют
    значения) получалось «5 000 тг тг»."""
    import re
    digits = re.sub(r"[^\d]", "", str(amount))
    if not digits:
        return str(amount)
    try:
        return f"{int(digits):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


_director_bot_cache: Bot | None = None


async def _get_director_bot() -> Bot:
    """Кэшированный клиент к директорскому боту. Создаётся один раз —
    переиспользуем session, SSL handshake не повторяется."""
    global _director_bot_cache
    if _director_bot_cache is None or _director_bot_cache.session.closed:
        token = os.getenv("ZVS_DIR_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("ZVS_DIR_BOT_TOKEN не задан — некуда слать заявки")
        _director_bot_cache = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _director_bot_cache


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
            f"Привет, <b>{name}</b>! Жми «💸 Подать заявку».",
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

    try:
        director_bot = await _get_director_bot()
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


# ────────────────────────────────────────────────────────────
# Подача заявки через Telegram WebApp (форма)
# ────────────────────────────────────────────────────────────

@router.message(F.web_app_data)
async def handle_web_app_form(message: Message, state: FSMContext):
    """Юзер заполнил форму в WebApp и нажал «Отправить директору».
    Tg-клиент шлёт нам сообщение с message.web_app_data.data — JSON."""
    if not _is_registered(message.from_user.id):
        await message.answer("🚫 Нет доступа. Сначала /start")
        return
    await state.clear()

    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
        amount = int(data.get("amount", 0))
        purpose = str(data.get("purpose", "")).strip()
        account = str(data.get("account", "")).strip()
    except (ValueError, json.JSONDecodeError):
        await message.answer("Не получилось прочитать форму. Попробуй ещё раз.")
        return

    # Валидация
    if amount <= 0 or amount > 100_000_000:
        await message.answer("Сумма некорректная. Открой форму заново.")
        return
    if len(purpose) < 3 or len(purpose) > 500:
        await message.answer("Описание слишком короткое или слишком длинное.")
        return
    if account not in BANKS:
        await message.answer("Неизвестный счёт. Открой форму заново.")
        return

    uid = message.from_user.id
    user = await asyncio.to_thread(get_user, uid)
    name = (user or {}).get("name") or message.from_user.full_name

    zvs_id = await asyncio.to_thread(create_request, uid, name, amount, purpose, account)
    if not zvs_id:
        await message.answer("❌ Не получилось создать заявку, попробуй ещё раз чуть позже.")
        return

    sent = await message.answer(
        f"⏳ <b>Заявка №{zvs_id}</b>\n"
        f"{_format_amount(amount)} тг · {account.capitalize()}\n"
        f"{purpose}",
        reply_markup=zvs_main_menu(),
    )
    # Запоминаем — чтоб при одобрении/отклонении ОТРЕДАКТИРОВАТЬ это сообщение,
    # а не слать новое
    await asyncio.to_thread(save_applicant_msg, zvs_id, sent.chat.id, sent.message_id)

    # Уведомление директору
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    try:
        director_bot = await _get_director_bot()
        await director_bot.send_message(
            DIRECTOR_ID,
            f"💸 <b>Новая ЗВС №{zvs_id}</b>\n\n"
            f"👤 {name} ({username})\n"
            f"💰 <b>{_format_amount(amount)} тг</b>\n"
            f"📝 {purpose}\n"
            f"🏦 {account.capitalize()}",
            reply_markup=director_decision_kb(zvs_id, uid),
        )
    except Exception as e:
        logger.error(f"notify director (webapp): {e}")


# ────────────────────────────────────────────────────────────
# Подача заявки — FSM (fallback если WebApp недоступен)
# ────────────────────────────────────────────────────────────

@router.message(Command("zayavka"))
@router.message(F.text == "💸 Подать заявку")
async def start_apply(message: Message, state: FSMContext):
    if not _is_registered(message.from_user.id):
        await message.answer("🚫 Нет доступа. Сначала /start")
        return
    await state.clear()
    await state.set_state(ZvsApply.waiting_amount)
    await message.answer("💰 Сумма?")


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
        await message.answer("Только число. Например: 50000")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    if amount > 100_000_000:
        await message.answer("Слишком большая. Проверь нолики.")
        return

    await state.update_data(amount=amount)
    await state.set_state(ZvsApply.waiting_purpose)
    await message.answer("📝 На что?")


@router.message(ZvsApply.waiting_purpose)
async def step_purpose(message: Message, state: FSMContext):
    purpose = (message.text or "").strip()
    if len(purpose) < 3:
        await message.answer("Коротко напиши пару слов.")
        return
    if len(purpose) > 500:
        await message.answer("Слишком длинно (макс 500 символов).")
        return

    await state.update_data(purpose=purpose)
    await state.set_state(ZvsApply.waiting_account)
    await message.answer("🏦 Счёт:", reply_markup=accounts_kb())


@router.callback_query(F.data.startswith("zvs_acc:"), ZvsApply.waiting_account)
async def step_account(callback: CallbackQuery, state: FSMContext):
    # Сразу ack — иначе у юзера крутится спинер до конца обработки
    await callback.answer()

    account = callback.data.split(":", 1)[1]
    if account not in BANKS:
        await callback.answer("Битый счёт", show_alert=True)
        return

    await state.update_data(account=account)
    data = await state.get_data()
    await state.set_state(ZvsApply.waiting_confirm)

    text = (
        f"<b>{_format_amount(data['amount'])} тг</b> · {account.capitalize()}\n"
        f"{data['purpose']}"
    )
    try:
        await callback.message.edit_text(text, reply_markup=confirm_apply_kb())
    except Exception:
        await callback.message.answer(text, reply_markup=confirm_apply_kb())


@router.callback_query(F.data == "zvs_apply:cancel", ZvsApply.waiting_confirm)
async def confirm_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("Отменено. Заявка не отправлена.")
    except Exception:
        pass


@router.callback_query(F.data == "zvs_apply:send", ZvsApply.waiting_confirm)
async def confirm_send(callback: CallbackQuery, state: FSMContext):
    # Сразу ack — чтоб у юзера спинер не висел пока мы пишем в Sheets
    await callback.answer("Отправляю…")

    data = await state.get_data()
    amount = data.get("amount")
    purpose = data.get("purpose", "")
    account = data.get("account", "")
    uid = callback.from_user.id

    user = await asyncio.to_thread(get_user, uid)
    user = user or {}
    name = user.get("name") or callback.from_user.full_name

    # Создание заявки в Sheets — в отдельном потоке (не блокируем event loop)
    zvs_id = await asyncio.to_thread(
        create_request, uid, name, amount, purpose, account
    )
    if not zvs_id:
        await callback.message.edit_text(
            "❌ Не получилось создать заявку (проблема с таблицей). "
            "Попробуй ещё раз чуть позже или напиши директору."
        )
        await state.clear()
        return

    # Подтверждение заявителю — редактируем сообщение и запоминаем его id,
    # чтоб директор при одобрении тут же поменял статус (а не слал новое)
    try:
        await callback.message.edit_text(
            f"⏳ <b>Заявка №{zvs_id}</b>\n"
            f"{_format_amount(amount)} тг · {account.capitalize()}\n"
            f"{purpose}"
        )
        await asyncio.to_thread(save_applicant_msg, zvs_id, callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass

    # Уведомление директору — через ОТДЕЛЬНЫЙ директорский бот (кэшированный)
    username = f"@{callback.from_user.username}" if callback.from_user.username else "—"
    try:
        director_bot = await _get_director_bot()
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
    reqs = await asyncio.to_thread(get_user_requests, uid, 10)
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
