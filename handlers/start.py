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
            f"\ud83d\udc4b Privet, <b>{user['name']}</b>!\nRol: <b>{role}</b>",
            reply_markup=main_menu(role)
        )
        return
    await message.answer(
        "\ud83d\udc4b Dobro pozhalovat!\nVyberite vashe imya:",
        reply_markup=build_names_kb()
    )
    await state.set_state(AuthStates.choosing_name)


@router.callback_query(F.data.startswith("auth:"))
async def auth_callback(call: CallbackQuery, state: FSMContext):
    name = call.data.split(":", 1)[1]
    user_data = register(call.from_user.id, name)
    role = user_data["role"]
    await call.message.answer(
        f"\u2705 Privet, <b>{name}</b>!\nRol: <b>{role}</b>",
        reply_markup=main_menu(role)
    )
    await call.answer()
    await state.clear()


@router.message(F.text == "\ud83d\udc64 Moy profil")
async def my_profile(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. Napishi /start")
        return
    role = user.get("role", "\u2014")
    name = user.get("name", "\u2014")
    registered = user.get("registered_at", "\u2014")
    await message.answer(
        f"\ud83d\udc64 <b>Moy profil</b>\n\n"
        f"Imya: <b>{name}</b>\n"
        f"Rol: <b>{role}</b>\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Registratsiya: {registered}"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "\ud83d\udcd6 <b>Komandy:</b>\n"
        "/start \u2014 Nachalo\n"
        "/help \u2014 Pomosh\n\n"
        "\ud83d\udcb3 <b>Vnesit oplatu</b> \u2014 dobavit novuyu oplatu\n"
        "\ud83d\udcca <b>Otchety</b> \u2014 prosmotr otchetov\n"
        "\ud83d\udc64 <b>Moy profil</b> \u2014 vashi dannye"
    )
