import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import PaymentStates
from keyboards.payment import categories_kb, license_types_kb, periods_kb, banks_kb, confirm_kb
from services.sheets import add_payment
from services.users import get_user_info
from keyboards.main import cancel_kb

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text == "Vnesit oplatu")
async def start_payment(message: Message, state: FSMContext):
    await state.clear()
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    await state.update_data(manager=user['name'])
    await message.answer("Vyberite kategoriu:", reply_markup=categories_kb())
    await state.set_state(PaymentStates.choose_category)

@router.callback_query(PaymentStates.choose_category, F.data.startswith("cat:"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":", 1)[1]
    await state.update_data(category=cat_id)
    await callback.message.edit_text("Tip litsenzii:", reply_markup=license_types_kb())
    await state.set_state(PaymentStates.choose_license)
    await callback.answer()

@router.callback_query(PaymentStates.choose_license, F.data.startswith("lt:"))
async def choose_license(callback: CallbackQuery, state: FSMContext):
    lt = callback.data.split(":", 1)[1]
    await state.update_data(license_type=lt)
    await callback.message.edit_text("Vvedite nazvanie klienta:")
    await state.set_state(PaymentStates.enter_client)
    await callback.answer()

@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    from keyboards.payment import periods_kb
    await message.answer("Vyberte period:", reply_markup=periods_kb())
    await state.set_state(PaymentStates.choose_period)

@router.callback_query(PaymentStates.choose_period, F.data.startswith("period:"))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":", 1)[1]
    await state.update_data(period=period)
    await callback.message.edit_text("Vvedite summu (tsifry):")
    await state.set_state(PaymentStates.enter_amount)
    await callback.answer()

@router.message(PaymentStates.enter_amount)
async def enter_amount(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await message.answer("Vvedite chislo, naprimer: 50000")
        return
    await state.update_data(amount=amount)
    from keyboards.payment import banks_kb
    await message.answer("Vyberte bank:", reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)

@router.callback_query(PaymentStates.choose_bank, F.data.startswith("bank:"))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(":", 1)[1]
    await state.update_data(bank=bank)
    data = await state.get_data()
    text = (
        f"Proverka:\n"
        f"Kategoria: {data['category']}\n"
        f"Litsenziya: {data['license_type']}\n"
        f"Klient: {data['client']}\n"
        f"Period: {data['period']}\n"
        f"Summa: {data['amount']}\n"
        f"Bank: {bank}\n"
        f"Manager: {data['manager']}"
    )
    await callback.message.edit_text(text, reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await callback.answer()

@router.callback_query(PaymentStates.confirm, F.data == "confirm")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        save_payment(data)
        await callback.message.edit_text("Oplata zapisana!")
    except Exception as e:
        logger.error(f"save_payment error: {e}")
        await callback.message.edit_text(f"Oshibka zapisi: {e}")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Otmeneno.")
    await callback.answer()
