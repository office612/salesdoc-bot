"""
Получаем ссылку на фото из Telegram и сохраняем в таблицу.
"""
import logging

logger = logging.getLogger(__name__)


async def upload_receipt(
    file_bytes: bytes,
    filename: str,
    year: int,
    month: int,
    mime_type: str = "image/jpeg",
    bot=None,
    file_id: str = "",
) -> str:
    """Возвращает ссылку на фото в Telegram."""
    if bot and file_id:
        file = await bot.get_file(file_id)
        link = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        logger.info(f"Receipt link: {filename} -> {link}")
        return link
    return ""
