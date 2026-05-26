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
from handlers import zvs as zvs_handlers
from handlers import zvs_director as zvs_director_handlers

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
    kassa_bot = None
    kassa_dp = None
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
    else:
        logger.warning("KASSA_BOT_TOKEN не задан — касса-бот не запущен")

    # ── Бот ЗВС @SDzvsbot ──
    zvs_token = os.getenv("ZVS_BOT_TOKEN", "")
    zvs_bot = None
    zvs_dp = None
    if zvs_token:
        zvs_bot = Bot(
            token=zvs_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        zvs_dp = Dispatcher(storage=MemoryStorage())
        zvs_dp.include_router(zvs_handlers.router)
        await zvs_bot.delete_webhook(drop_pending_updates=True)
        # Инициализируем таблицу заранее — чтоб директор видел листы до первой заявки
        try:
            from services.zvs_sheets import get_zvs_sheet
            await asyncio.to_thread(get_zvs_sheet)
            logger.info("ЗВС таблица инициализирована (листы requests + Итоги)")
        except Exception as e:
            logger.error(f"Не удалось инициализировать ЗВС таблицу: {e}")
        logger.info("ЗВС-бот для сотрудников запущен")
    else:
        logger.warning("ZVS_BOT_TOKEN не задан — ЗВС-бот сотрудников не запущен")

    # ── Бот ЗВС для директора ──
    zvs_dir_token = os.getenv("ZVS_DIR_BOT_TOKEN", "")
    zvs_dir_bot = None
    zvs_dir_dp = None
    if zvs_dir_token:
        zvs_dir_bot = Bot(
            token=zvs_dir_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        zvs_dir_dp = Dispatcher(storage=MemoryStorage())
        zvs_dir_dp.include_router(zvs_director_handlers.router)
        await zvs_dir_bot.delete_webhook(drop_pending_updates=True)
        logger.info("ЗВС-бот для директора запущен")
    else:
        logger.warning("ZVS_DIR_BOT_TOKEN не задан — ЗВС-бот директора не запущен")

    # ── Запуск всех ботов параллельно ──
    tasks = [
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=30)
    ]
    if kassa_bot and kassa_dp:
        tasks.append(
            kassa_dp.start_polling(kassa_bot, allowed_updates=kassa_dp.resolve_used_update_types(), polling_timeout=30)
        )
    if zvs_bot and zvs_dp:
        tasks.append(
            zvs_dp.start_polling(zvs_bot, allowed_updates=zvs_dp.resolve_used_update_types(), polling_timeout=30)
        )
    if zvs_dir_bot and zvs_dir_dp:
        tasks.append(
            zvs_dir_dp.start_polling(zvs_dir_bot, allowed_updates=zvs_dir_dp.resolve_used_update_types(), polling_timeout=30)
        )

    try:
        await asyncio.gather(*tasks)
    finally:
        await bot.session.close()
        if kassa_bot:
            await kassa_bot.session.close()
        if zvs_bot:
            await zvs_bot.session.close()
        if zvs_dir_bot:
            await zvs_dir_bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
