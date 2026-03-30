import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery

from config import BOT_TOKEN
from handlers import start, payment, reports

from services.sheets import mark_planted

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Роутер для @kassasdkzbot — обработка кнопки «Посажено» ──
kassa_router = Router()

@kassa_router.callback_query(F.data.startswith("planted:"))
async def planted_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверные данные", show_alert=True)
        return
    row_num = int(parts[1])
    month = int(parts[2])
    ok = mark_planted(row_num, month)
    if ok:
        if callback.message.photo or callback.message.document:
            # Фото/файл — используем edit_caption
            old_caption = callback.message.caption or ""
            await callback.message.edit_caption(
                caption=old_caption + "\n\n✅ <b>ПОСАЖЕНО</b>",
                parse_mode="HTML",
                reply_markup=None
            )
        else:
            # Текстовое сообщение — используем edit_text
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>ПОСАЖЕНО</b>",
                parse_mode="HTML",
                reply_markup=None
            )
    else:
        await callback.answer("❌ Ошибка при посадке.", show_alert=True)
    await callback.answer()

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

    # ── Бот кассы @kassasdkzbot ──
    kassa_token = os.getenv("KASSA_BOT_TOKEN", "")

    if kassa_token:
        kassa_bot = Bot(
            token=kassa_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        kassa_dp = Dispatcher()
        kassa_dp.include_router(kassa_router)

        await kassa_bot.delete_webhook(drop_pending_updates=True)
        logger.info("Касса-бот (@kassasdkzbot) запущен")

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
