import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

from services.users import get_user_info, register
from keyboards.main import main_menu
from config import LEADER, EMPLOYEES

router = Router()
logger = logging.getLogger(__name__)

ALL_NAMES = EMPLOYEES["managers"] + EMPLOYEES["accountants"] + [LEADER]


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = get_user_info(message.from_user.id)
    if user:
        role = user.get("role", "menedzher")
        name = user.get("name", "")
        await message.answer(
            "<b>" + name + "</b>, добро пожаловать!\nРоль: " + role,
            reply_markup=main_menu(role)
        )
    else:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=n)] for n in ALL_NAMES],
            resize_keyboard=True
        )
        await message.answer("Выбери своё имя:", reply_markup=kb)


@router.message(F.text.in_(ALL_NAMES))
async def select_name(message: Message):
    name = message.text
    user_data = register(message.from_user.id, name)
    role = user_data["role"]
    await message.answer(
        "<b>" + name + "</b> зарегистрирован!\nРоль: " + role,
        reply_markup=main_menu(role)
    )


@router.message(F.text == "\U0001F464 Мой профиль")
async def my_profile(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Не авторизован. /start")
        return
    name = user.get("name", "—")
    role = user.get("role", "—")
    reg = user.get("registered_at", "—")
    await message.answer(
        "<b>Профиль</b>\n\nИмя: <b>" + name + "</b>\nРоль: <b>" + role + "</b>\nЗарег: " + reg
    )
