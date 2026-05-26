import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery

from config import BOT_TOKEN, DIRECTOR_ID, ACCOUNTANT_IDS
from handlers import start, payment, reports, subscription

from services.sheets import mark_planted, get_user
from services.planted_store import get_messages


def _has_kassa_access(uid: int) -> bool:
    """Доступ к кнопкам в @SDfinansbot. Whitelist по ID + по users sheet."""
    if uid == DIRECTOR_ID:
        return True
    if uid in ACCOUNTANT_IDS:
        return True
    if get_user(uid):
        return True
    return False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Роутер для @SDfinansbot — обработка кнопки «Посажено» ──
kassa_router = Router()

@kassa_router.callback_query(F.data.startswith("planted:"))
async def planted_handler(callback: CallbackQuery):
    if not _has_kassa_access(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверные данные", show_alert=True)
        return
    rows_str = parts[1]  # может быть "8" или "8,9,10"
    month = int(parts[2])

    # Маркируем ВСЕ строки как посаженные
    row_nums = [int(r) for r in rows_str.split(",")]
    all_ok = True
    for row_num in row_nums:
        ok = mark_planted(row_num, month)
        if not ok:
            all_ok = False

    if not all_ok:
        await callback.answer("❌ Ошибка при посадке.", show_alert=True)
        return

    # Редактируем сообщение того кто нажал
    planted_label = f"\n\n✅ <b>ПОСАЖЕНО</b> (строки: {rows_str})"
    try:
        if callback.message.photo or callback.message.document:
            old_caption = callback.message.caption or ""
            await callback.message.edit_caption(
                caption=old_caption + planted_label,
                parse_mode="HTML",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                callback.message.text + planted_label,
                parse_mode="HTML",
                reply_markup=None
            )
    except Exception as e:
        logger.error(f"Edit own planted msg: {e}")

    # Редактируем сообщения ДРУГИХ пользователей
    planted_key = f"{rows_str}:{month}"
    stored = get_messages(planted_key)
    clicker_chat = callback.message.chat.id
    for chat_id, msg_id in stored:
        if chat_id == clicker_chat:
            continue
        try:
            # Убираем кнопку и отправляем уведомление
            await callback.bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=msg_id, reply_markup=None
            )
        except Exception:
            pass
        try:
            await callback.bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>ПОСАЖЕНО</b> (строки: {rows_str})",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Notify other planted {chat_id}: {e}")

    await callback.answer("✅ Посажено!")

async def main():
    # ── Основной бот @sakesdocbot ──
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(payment.router)
    dp.include_router(reports.router)

    logger.info("Бот запущен")

    # Убиваем старый webhook/polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook удалён, старые апдейты очищены")

    # ── Бот кассы @SDfinansbot ──
    kassa_token = os.getenv("KASSA_BOT_TOKEN", "")

    if kassa_token:
        kassa_bot = Bot(
            token=kassa_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        kassa_dp = Dispatcher()
        kassa_dp.include_router(kassa_router)
        kassa_dp.include_router(subscription.router)

        await kassa_bot.delete_webhook(drop_pending_updates=True)
        logger.info("Касса-бот (@SDfinansbot) запущен")

        try:
            # Запускаем оба бота параллельно
            await asyncio.gather(
                dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=30),
                kassa_dp.start_polling(kassa_bot, allowed_updates=kassa_dp.resolve_used_update_types(), polling_timeout=30),
            )
        finally:
            await bot.session.close()
            await kassa_bot.session.close()
    else:
        logger.warning("KASSA_BOT_TOKEN не задан — касса-бот не запущен")
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=30)
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
