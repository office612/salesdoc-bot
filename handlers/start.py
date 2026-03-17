import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from services.users import get_user_info, fix_legacy_name
from services.sheets import get_or_create_users_sheet, register_user
from keyboards.main import main_menu
from config import DIRECTOR_ID

router = Router()
logger = logging.getLogger(__name__)

ROLE_LABELS = {
    "menedzher":   "Менеджер",
    "buhgalter":   "Бухгалтер",
    "rukovoditel": "Руководитель",
}


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer(
            "🚫 <b>Нет доступа.</b>\n\n"
            "Обратитесь к руководителю для получения доступа к боту.\n"
            "Сообщите ему свой Telegram ID: <code>"
            + str(message.from_user.id) + "</code>"
        )
        try:
            tg = message.from_user
            username = f"@{tg.username}" if tg.username else "нет username"
            await message.bot.send_message(
                DIRECTOR_ID,
                f"🔔 <b>Запрос доступа</b>\n\n"
                f"ID: <code>{tg.id}</code>\n"
                f"Имя: {tg.full_name}\n"
                f"Username: {username}\n\n"
                f"Чтобы добавить:\n"
                f"<code>/add {tg.id} ИМЯ РОЛЬ</code>\n"
                f"Роли: menedzher / buhgalter / rukovoditel"
            )
        except Exception as e:
            logger.warning(f"notify director failed: {e}")
        return

    user = fix_legacy_name(message.from_user.id, user)
    role = user.get("role", "menedzher")
    name = user.get("name", "")
    role_label = ROLE_LABELS.get(role, role)
    await message.answer(
        f"<b>{name}</b>, добро пожаловать! 👋\nРоль: {role_label}",
        reply_markup=main_menu(role)
    )


@router.message(Command("add"))
async def cmd_add(message: Message):
    if message.from_user.id != DIRECTOR_ID:
        await message.answer("🚫 Нет прав.")
        return

    parts = message.text.strip().split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            "❌ Формат: <code>/add 123456789 Айдос Хапез menedzher</code>\n\n"
            "Роли:\n"
            "• <code>menedzher</code> — менеджер\n"
            "• <code>buhgalter</code> — бухгалтер\n"
            "• <code>rukovoditel</code> — руководитель"
        )
        return

    _, tg_id_str, name, role = parts
    valid_roles = ("menedzher", "buhgalter", "rukovoditel")

    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return

    if role not in valid_roles:
        await message.answer(
            f"❌ Неверная роль: <code>{role}</code>\n"
            f"Допустимые: {', '.join(valid_roles)}"
        )
        return

    try:
        register_user(tg_id, name, role)
        role_label = ROLE_LABELS.get(role, role)
        await message.answer(
            f"✅ Пользователь добавлен:\n\n"
            f"👤 <b>{name}</b>\n"
            f"🆔 <code>{tg_id}</code>\n"
            f"🎭 {role_label}"
        )
        try:
            await message.bot.send_message(
                tg_id,
                f"✅ <b>Доступ открыт!</b>\n\n"
                f"Привет, <b>{name}</b>! Теперь ты можешь работать в боте.\n"
                f"Нажми /start чтобы начать."
            )
        except Exception:
            await message.answer("⚠️ Пользователь добавлен, но уведомить его не удалось (он ещё не писал боту).")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("remove"))
async def cmd_remove(message: Message):
    if message.from_user.id != DIRECTOR_ID:
        await message.answer("🚫 Нет прав.")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Формат: <code>/remove 123456789</code>")
        return

    try:
        tg_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return

    try:
        ws = get_or_create_users_sheet()
        rows = ws.get_all_values()
        removed = False
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[0]) == str(tg_id):
                name = row[1] if len(row) > 1 else "?"
                ws.delete_rows(i)
                await message.answer(f"✅ Пользователь <b>{name}</b> (<code>{tg_id}</code>) удалён.")
                removed = True
                break
        if not removed:
            await message.answer(f"❌ Пользователь с ID <code>{tg_id}</code> не найден.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("users"))
async def cmd_users(message: Message):
    if message.from_user.id != DIRECTOR_ID:
        await message.answer("🚫 Нет прав.")
        return

    try:
        ws = get_or_create_users_sheet()
        rows = ws.get_all_values()
        if len(rows) <= 1:
            await message.answer("📋 Нет зарегистрированных пользователей.")
            return

        lines = ["📋 <b>Зарегистрированные пользователи:</b>\n"]
        for row in rows[1:]:
            if not row or not str(row[0]).strip():
                continue
            tg_id = row[0] if len(row) > 0 else "?"
            name  = row[1] if len(row) > 1 else "?"
            role  = row[2] if len(row) > 2 else "?"
            reg   = row[3] if len(row) > 3 else "?"
            role_label = ROLE_LABELS.get(role, role)
            lines.append(f"👤 <b>{name}</b> | {role_label}\n🆔 <code>{tg_id}</code> | {reg}")

        await message.answer("\n\n".join(lines))
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(F.text == "\U0001F464 Мой профиль")
async def my_profile(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Не авторизован. /start")
        return
    name = user.get("name", "—")
    role = user.get("role", "—")
    reg  = user.get("registered_at", "—")
    role_label = ROLE_LABELS.get(role, role)
    await message.answer(
        f"<b>Профиль</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"Роль: <b>{role_label}</b>\n"
        f"Зарег: {reg}\n"
        f"TG ID: <code>{message.from_user.id}</code>"
    )
