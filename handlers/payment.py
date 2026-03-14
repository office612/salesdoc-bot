import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import PaymentStates
from keyboards.payment import (
    categories_kb, license_types_kb, periods_kb,
    banks_kb, confirm_kb, skip_kb
)
from services.sheets import add_payment
from services.users import get_user_info
from keyboards.main import main_menu

logger = logging.getLogger(__name__)
router = Router()


def format_summary(data: dict) -> str:
    return (
        f"📋 <b>Проверка:</b>\n\n"
        f"📦 Категория: <b>{data.get('category', '—')}</b>\n"
        f"📄 Лицензия: <b>{data.get('license_type', '—')}</b>\n"
        f"🏢 Клиент: <b>{data.get('client', '—')}</b>\n"
        f"⏱ Период: <b>{data.get('period', '—')}</b>\n"
        f"💰 Сумма: <b>{data.get('amount', '—')}</b>\n"
        f"🏦 Банк: <b>{data.get('bank', '—')}</b>\n"
        f"👤 Менеджер: <b>{data.get('manager', '—')}</b>\n"
        f"💬 Коммент: <b>{data.get('comment', '—')}</b>"
    )


@router.message(F.text == "💳 Внести оплату")
async def start_payment(message: Message, state: FSMContext):
    await state.clear()
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Не авторизован. Напиши /start")
        return
    await state.update_data(manager=user['name'])
    await message.answer("📦 Выберите категорию:", reply_markup=categories_kb())
    await state.set_state(PaymentStates.choose_category)


@router.callback_query(PaymentStates.choose_category, F.data.startswith("cat:"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":", 1)[1]
    await state.update_data(category=cat_id)
    await callback.message.edit_text("📄 Тип лицензии:", reply_markup=license_types_kb())
    await state.set_state(PaymentStates.choose_license)
    await callback.answer()


@router.callback_query(PaymentStates.choose_license, F.data.startswith("lt:"))
async def choose_license(callback: CallbackQuery, state: FSMContext):
    lt = callback.data.split(":", 1)[1]
    await state.update_data(license_type=lt)
    await callback.message.edit_text("🏢 Введите название клиента:")
    await state.set_state(PaymentStates.enter_client)
    await callback.answer()


@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    await message.answer("⏱ Выберите период:", reply_markup=periods_kb())
    await state.set_state(PaymentStates.choose_period)


@router.callback_query(PaymentStates.choose_period, F.data.startswith("period:"))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":", 1)[1]
    await state.update_data(period=period)
    await callback.message.edit_text("💰 Введите сумму (цифры):")
    await state.set_state(PaymentStates.enter_amount)
    await callback.answer()


@router.message(PaymentStates.enter_amount)
async def enter_amount(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await message.answer("❌ Введите число, например: 50000")
        return
    await state.update_data(amount=amount)
    await message.answer("🏦 Выберите банк:", reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)


@router.callback_query(PaymentStates.choose_bank, F.data.startswith("bank:"))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(":", 1)[1]
    await state.update_data(bank=bank, comment="")
    data = await state.get_data()
    text = format_summary(data)
    await callback.message.edit_text(text, reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await callback.answer()


@router.callback_query(PaymentStates.confirm, F.data == "pay_confirm")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_data = {
        "company": data.get("client", ""),
        "category_raw": data.get("category", ""),
        "license_type": data.get("license_type", ""),
        "license_qty": "",
        "manager": data.get("manager", ""),
        "license_rate": "",
        "price": "",
        "period": data.get("period", ""),
        "amount": data.get("amount", ""),
        "bank": data.get("bank", ""),
        "comment": data.get("comment", ""),
    }
    try:
        row_num = add_payment(payment_data)
        await callback.message.edit_text(
            f"✅ Оплата записана! (строка {row_num})\n\n"
            f"🏢 {data.get('client')} — {data.get('amount')} tng"
        )
    except Exception as e:
        logger.error(f"add_payment error: {e}")
        await callback.message.edit_text(f"❌ Ошибка записи: {e}")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()
