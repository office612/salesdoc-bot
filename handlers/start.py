import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from states import AuthStates
from services.users import get_user_info, register, get_all_names, get_role
from keyboards.main import main_menu
from config import LEADER

logger = logging.getLogger(__name__)
router = Router()


def build_names_kb():
    names = get_all_names() + [LEADER]
    rows = []
    for i in range(0, len(names), 2):
        row = [InlineKeyboardButton(text=n, callback_data=f"auth:{n}") for n in names[i:i+2]]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = get_user_info(message.from_user.id)
    if user:
        role = user.get("role", "menedzher")
        await message.answer(
            f"👋 Привет, <b>{user['name']}</b>!\nРоль: <b>{role}</b>",
            reply_markup=main_menu(role)
        )
        return
    await message.answer(
        "👋 Добро пожаловать!\nВыберите ваше имя:",
        reply_markup=build_names_kb()
    )
    await state.set_state(AuthStates.choosing_name)


@router.callback_query(F.data.startswith("auth:"))
async def auth_callback(call: CallbackQuery, state: FSMContext):
    name = call.data.split(":", 1)[1]
    user_data = register(call.from_user.id, name)
    role = user_data["role"]
    await call.message.answer(
        f"✅ Привет, <b>{name}</b>!\nРоль: <b>{role}</b>",
        reply_markup=main_menu(role)
    )
    await call.answer()
    await state.clear()


@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Не авторизован. Напиши /start")
        return
    role = user.get("role", "—")
    name = user.get("name", "—")
    registered = user.get("registered_at", "—")
    await message.answer(
        f"👤 <b>Мой профиль</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"Роль: <b>{role}</b>\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Регистрация: {registered}"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Команды:</b>\n"
        "/start — Начало\n"
        "/help — Помощь\n\n"
        "💳 <b>Внести оплату</b> — добавить оплату\n"
        "📊 <b>Отчёты</b> — просмотр отчётов\n"
        "👤 <b>Мой профиль</b> — ваши данные"
    )
