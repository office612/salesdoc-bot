import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import PaymentStates
from keyboards.payment import (
    package_kb, categories_kb, license_types_kb, periods_kb,
    banks_kb, confirm_kb, skip_receipt_kb, months_kb, confirm_price_kb,
    payment_date_kb, bot_periods_kb, manual_amount_kb, add_service_kb,
    back_button, service_categories_kb,
)
from services.sheets import add_payment
from services.users import get_user_info, is_accountant, is_manager
from config import (
    CATEGORIES, DIRECTOR_ID, ACCOUNTANT_IDS, MONTH_SHEETS,
    PRICES_NEW, PRICES_OLD, TIMEZONE, EMPLOYEES, LEADER,
    SERVICE_CATS, STATUS_CATS, PERIOD_MONTHS, NEW_CLIENT_DATE,
    MANUAL_AMOUNT_CATS, BOT_CATS,
)
from datetime import datetime, date
import pytz

logger = logging.getLogger(__name__)
router = Router()


# ═══════════════════════════════════════════════════════════════════════════════
# СТАРТ ЗАПИСИ ОПЛАТЫ
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "new_payment")
async def start_payment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Вы не авторизованы", show_alert=True)
        return
    await state.update_data(manager=user["name"])
    await callback.message.edit_text("Выберите месяц:", reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)


@router.callback_query(PaymentStates.choose_month, F.data.startswith("month:"))
async def choose_month(callback: CallbackQuery, state: FSMContext):
    month_num = int(callback.data.split(":")[1])
    month_name = MONTH_SHEETS[month_num]
    await state.update_data(month=month_num, month_name=month_name)
    await callback.message.edit_text(
        f"Месяц: {month_name}\nВыберите статью:",
        reply_markup=categories_kb()
    )
    await state.set_state(PaymentStates.choose_category)


@router.callback_query(PaymentStates.choose_category, F.data == "cat:show_all")
async def show_all_categories(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=categories_kb(show_all=True))


@router.callback_query(PaymentStates.choose_category, F.data.startswith("cat:"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.split(":")[1]
    cat_label = next((label for key, label in CATEGORIES if key == cat_key), cat_key)
    await state.update_data(category_key=cat_key, category=cat_label)

    # Услуги идут напрямую к клиенту
    if cat_key in SERVICE_CATS:
        await callback.message.edit_text(
            f"Статья: {cat_label}\nВведите название клиента:"
        )
        await state.set_state(PaymentStates.enter_client)
    else:
        # Лицензии/абон плата → выбор типа лицензии
        await callback.message.edit_text(
            f"Статья: {cat_label}\nВыберите тип лицензии:",
            reply_markup=license_types_kb()
        )
        await state.set_state(PaymentStates.choose_license)


@router.callback_query(PaymentStates.choose_license, F.data.startswith("lic:"))
async def choose_license(callback: CallbackQuery, state: FSMContext):
    lic_type = callback.data.split(":")[1]
    await state.update_data(license_type=lic_type)
    await callback.message.edit_text(
        f"Тип: {lic_type}\nВведите название клиента:"
    )
    await state.set_state(PaymentStates.enter_client)

