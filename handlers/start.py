import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from states import AuthStates
from services.users import get_user_info, register, get_all_names
from keyboards.main import main_menu

logger = logging.getLogger(__name__)
router = Router()


def build_names_kb():
    names = get_all_names()
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
        await message.answer(
            f"Privet! <b>{user['name']}</b>",
            parse_mode="HTML",
            reply_markup=main_menu(user.get("role", ""))
        )
        return
    await message.answer(
        "Dobro pozhalovat! Vyberite vashe imya:",
        reply_markup=build_names_kb()
    )
    await state.set_state(AuthStates.choosing_name)


@router.callback_query(F.data.startswith("auth:"))
async def auth_callback(call: CallbackQuery, state: FSMContext):
    name = call.data.split(":", 1)[1]
    user_data = register(call.from_user.id, name)
    await call.message.answer(
        f"Privet, <b>{name}</b>! Rol: {user_data['role']}",
        parse_mode="HTML",
        reply_markup=main_menu(user_data["role"])
    )
    await call.answer()
    await state.clear()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Komandy:\n/start - Nachalo\n/help - Pomosh"
    )
