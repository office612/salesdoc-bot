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
        await message.answer(f"Привет! <b>{user['name']}</b>", reply_markup=main_menu(user['role']))
    else:
        await message.answer("Welcome! Choose name:", reply_markup=build_names_kb())
        await state.set_state(AuthStates.choose_name)

@router.callback_query(AuthStates.choose_name, F.data.startswith("auth:"))
async def process_auth(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 1)[1]
    user = register(callback.from_user.id, name)
    await callback.message.edit_text(f"Authorized as <b>{user['name']}</b>")
    await callback.message.answer("Menu:", reply_markup=main_menu(user["role"]))
    await state.clear()
    await callback.answer()
