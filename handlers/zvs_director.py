"""Хендлеры ЗВС-бота для директора.

Сюда приходят:
- Запросы регистрации новых сотрудников
- Новые заявки с кнопками [Одобрить][Отклонить][Доработка]
- При отклонении/доработке директор пишет причину следующим сообщением

Уведомления заявителю шлются через applicant_bot (отдельный бот сотрудников).
"""

import asyncio
import logging
import os
from aiogram import Router, F, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from states.zvs import ZvsDecision
from services.sheets import get_user, register_user
from services.zvs_sheets import get_request, update_decision
from services.zvs_pending import get as pending_get, remove as pending_remove
from services.zvs_messages import get as get_applicant_msg
from config import DIRECTOR_ID

logger = logging.getLogger(__name__)
router = Router()


def _format_amount(amount) -> str:
    """Робастно парсит число из чего угодно (с «тг», пробелами, запятыми)."""
    import re
    digits = re.sub(r"[^\d]", "", str(amount))
    if not digits:
        return str(amount)
    try:
        return f"{int(digits):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


async def _get_applicant_bot() -> Bot:
    """Создаём новый Bot каждый раз — кэш не надёжен, session может умереть.
    Создание Bot быстрое (~50мс), это окупается надёжностью."""
    token = os.getenv("ZVS_BOT_TOKEN", "")
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


# ────────────────────────────────────────────────────────────
# /start у директорского бота
# ────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != DIRECTOR_ID:
        await message.answer(
            "🚫 Это служебный бот SalesDoc — для одобрения заявок.\n"
            "У тебя нет доступа.\n\n"
            "Если ты сотрудник и хочешь подать заявку — открой @finzvsbot."
        )
        return
    await message.answer(
        "Мырзахыт, ты подключён к ЗВС-боту директора.\n\n"
        "Сюда будут прилетать:\n"
        "• Запросы доступа от новых сотрудников\n"
        "• Заявки на расход с кнопками Одобрить / Отклонить / Доработка\n\n"
        "Просто нажимай кнопки под уведомлением."
    )


# ────────────────────────────────────────────────────────────
# Одобрение новых сотрудников
# ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("zvs_reg:"))
async def handle_register(callback: CallbackQuery):
    if callback.from_user.id != DIRECTOR_ID:
        await callback.answer("Только директор", show_alert=True)
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

    # Сразу ack
    await callback.answer("Готово" if action == "ok" else "Отказано")

    pending = pending_get(tg_id) or {}
    name = pending.get("name") or "Сотрудник"
    applicant_bot = await _get_applicant_bot()

    try:
        if action == "ok":
            await asyncio.to_thread(register_user, tg_id, name, "employee")
            pending_remove(tg_id)
            try:
                await callback.message.edit_text(
                    callback.message.text + "\n\n✅ <b>Доступ открыт</b>"
                )
            except Exception:
                pass
            try:
                await applicant_bot.send_message(
                    tg_id,
                    "✅ Доступ к ЗВС-боту открыт!\n\nНажми /start чтобы начать."
                )
            except Exception as e:
                logger.warning(f"notify employee approved: {e}")
        else:
            pending_remove(tg_id)
            try:
                await callback.message.edit_text(
                    callback.message.text + "\n\n❌ <b>Отказано</b>"
                )
            except Exception:
                pass
            try:
                await applicant_bot.send_message(
                    tg_id,
                    "❌ В доступе отказано. Если ошибка — пиши директору лично."
                )
            except Exception:
                pass
    finally:
        try:
            await applicant_bot.session.close()
        except Exception:
            pass


# ────────────────────────────────────────────────────────────
# Кнопки решения по заявке
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

    # Сразу ack — остальная работа в фоне
    await callback.answer("Обрабатываю…" if action == "ap" else "")

    req = await asyncio.to_thread(get_request, zvs_id)
    if not req:
        await callback.message.answer(f"⚠️ Заявка №{zvs_id} не найдена в таблице.")
        return

    if req.get("status") and req["status"] != "Ожидает":
        await callback.message.answer(
            f"⚠️ Заявка №{zvs_id} уже {req['status'].lower()} "
            f"({req.get('decided_at', '')})"
        )
        return

    if action == "ap":
        ok = await asyncio.to_thread(update_decision, zvs_id, "Одобрено", "")
        if not ok:
            await callback.message.answer("❌ Не удалось записать в Sheets, попробуй ещё раз")
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
    ok = await asyncio.to_thread(update_decision, zvs_id, "Отклонено", text)
    if not ok:
        await message.answer("❌ Не удалось записать. Попробуй позже.")
        await state.clear()
        return
    req = await asyncio.to_thread(get_request, zvs_id) or {}
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
    ok = await asyncio.to_thread(update_decision, zvs_id, "На доработку", text)
    if not ok:
        await message.answer("❌ Не удалось записать. Попробуй позже.")
        await state.clear()
        return
    req = await asyncio.to_thread(get_request, zvs_id) or {}
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
    """Уведомить директора (отредактировать оригинал) и заявителя через @finzvsbot."""
    emoji = "✅" if status == "Одобрено" else ("❌" if status == "Отклонено" else "🔄")
    amount = _format_amount(req.get("amount", "—"))
    purpose = req.get("purpose", "—")
    name = req.get("name", "—")
    account = (req.get("account", "") or "—").capitalize()

    tail = ""
    if comment:
        tail = f"\n💬 {comment}"

    director_text = (
        f"{emoji} <b>{status.upper()}</b>\n\n"
        f"ЗВС №{zvs_id}\n"
        f"👤 {name}\n"
        f"💰 {amount} тг\n"
        f"📝 {purpose}\n"
        f"🏦 {account}"
        f"{tail}"
    )

    applicant_text = (
        f"{emoji} <b>Заявка №{zvs_id} — {status.lower()}</b>\n"
        f"{amount} тг · {account}\n"
        f"{purpose}"
        f"{tail}"
    )

    # event может быть CallbackQuery (одобрение в 1 нажатие) или Message (ввод причины)
    director_bot = event.bot
    applicant_bot = await _get_applicant_bot()

    async def update_director_msg():
        if hasattr(event, "message"):
            try:
                await event.message.edit_text(director_text, reply_markup=None)
                return
            except Exception:
                pass
        try:
            await director_bot.send_message(DIRECTOR_ID, director_text)
        except Exception:
            pass

    async def update_applicant_msg():
        loc = await asyncio.to_thread(get_applicant_msg, zvs_id)
        logger.info(f"[finalize] zvs_id={zvs_id} loc={loc}")
        if loc:
            chat_id, message_id = loc
            try:
                await applicant_bot.edit_message_text(
                    applicant_text,
                    chat_id=chat_id,
                    message_id=message_id,
                )
                logger.info(f"[finalize] edited applicant msg #{zvs_id} OK")
                return
            except Exception as e:
                logger.warning(f"[finalize] edit applicant msg #{zvs_id} FAILED: {type(e).__name__}: {e}")
        try:
            await applicant_bot.send_message(applicant_uid, applicant_text)
            logger.info(f"[finalize] sent NEW msg to applicant #{zvs_id} (fallback)")
        except Exception as e:
            logger.error(f"notify applicant {applicant_uid}: {e}")

    # Обе операции параллельно — экономит ~500мс
    try:
        await asyncio.gather(
            update_director_msg(),
            update_applicant_msg(),
        )
    finally:
        try:
            await applicant_bot.session.close()
        except Exception:
            pass


# ────────────────────────────────────────────────────────────
# Fallback для любого другого сообщения
# ────────────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        return
    if message.from_user.id != DIRECTOR_ID:
        await message.answer("🚫 Это служебный бот директора. Доступа нет.")
        return
    await message.answer(
        "Не понял. Жди заявки от сотрудников — будут приходить с кнопками."
    )
