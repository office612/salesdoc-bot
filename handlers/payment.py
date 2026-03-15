import logging
from datetime import datetime
import pytz
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import PaymentStates
from keyboards.payment import (
    categories_kb, license_types_kb, periods_kb, banks_kb, confirm_kb, skip_kb
)
from services.sheets import add_payment
from services.users import get_user_info
from keyboards.main import main_menu
from config import DIRECTOR_ID, ACCOUNTANT_IDS, MONTH_SHEETS, TIMEZONE

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
        f"👤 Менеджер: <b>{data.get('manager', '—')}</b>"
    )


def build_notification(data: dict, row_num: int) -> str:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_name = MONTH_SHEETS.get(now.month, '')
    try:
        amt = float(str(data.get('amount', 0)).replace(',', '.').replace(' ', ''))
        amt_fmt = '{:,.0f}'.format(amt).replace(',', ' ')
    except Exception:
        amt_fmt = str(data.get('amount', ''))
    return (
        f"💰 <b>Новая оплата #{row_num}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 {now.strftime('%d.%m.%Y %H:%M')} | {month_name}\n"
        f"👤 Менеджер: <b>{data.get('manager', '—')}</b>\n"
        f"🏢 Клиент: <b>{data.get('client', '—')}</b>\n"
        f"💵 Сумма: <b>{amt_fmt} тг</b>\n"
        f"🏦 Банк: <b>{data.get('bank', '—')}</b>\n"
        f"📊 Доходы KZ 2026 → строка {row_num}"
    )


async def notify_all(bot: Bot, data: dict, row_num: int):
    text = build_notification(data, row_num)
    for uid in [DIRECTOR_ID] + ACCOUNTANT_IDS:
        try:
            await bot.send_message(uid, text)
        except Exception as e:
            logger.warning(f'notify failed {uid}: {e}')


@router.message(F.text == '💳 Внести оплату')
async def start_payment(message: Message, state: FSMContext):
    await state.clear()
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer('Не авторизован. Напиши /start')
        return
    await state.update_data(manager=user['name'])
    await message.answer('📦 Выберите категорию:', reply_markup=categories_kb())
    await state.set_state(PaymentStates.choose_category)


@router.callback_query(PaymentStates.choose_category, F.data.startswith('cat:'))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(':', 1)[1]
    await state.update_data(category=cat_id)
    await callback.message.edit_text('📄 Тип лицензии:', reply_markup=license_types_kb())
    await state.set_state(PaymentStates.choose_license)
    await callback.answer()


@router.callback_query(PaymentStates.choose_license, F.data.startswith('lt:'))
async def choose_license(callback: CallbackQuery, state: FSMContext):
    lt = callback.data.split(':', 1)[1]
    await state.update_data(license_type=lt)
    await callback.message.edit_text('🏢 Введите название клиента:')
    await state.set_state(PaymentStates.enter_client)
    await callback.answer()


@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    await message.answer('⏱ Выберите период:', reply_markup=periods_kb())
    await state.set_state(PaymentStates.choose_period)


@router.callback_query(PaymentStates.choose_period, F.data.startswith('period:'))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(':', 1)[1]
    await state.update_data(period=period)
    await callback.message.edit_text('💰 Введите сумму (цифры):')
    await state.set_state(PaymentStates.enter_amount)
    await callback.answer()


@router.message(PaymentStates.enter_amount)
async def enter_amount(message: Message, state: FSMContext):
    text = message.text.strip().replace(' ', '').replace(',', '.')
    try:
        amount = float(text)
    except ValueError:
        await message.answer('❌ Введите число, например: 50000')
        return
    await state.update_data(amount=amount)
    await message.answer('🏦 Выберите банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)


@router.callback_query(PaymentStates.choose_bank, F.data.startswith('bank:'))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(':', 1)[1]
    await state.update_data(bank=bank, comment='')
    data = await state.get_data()
    await callback.message.edit_text(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await callback.answer()


@router.callback_query(PaymentStates.confirm, F.data == 'pay_confirm')
async def confirm_payment_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    payment_data = {
        'company':      data.get('client', ''),
        'category_raw': data.get('category', ''),
        'license_type': data.get('license_type', ''),
        'license_qty':  '',
        'manager':      data.get('manager', ''),
        'license_rate': '',
        'price':        '',
        'period':       data.get('period', ''),
        'amount':       data.get('amount', ''),
        'bank':         data.get('bank', ''),
        'comment':      data.get('comment', ''),
        'client':       data.get('client', ''),
        'category':     data.get('category', ''),
    }
    try:
        row_num = add_payment(payment_data)
        await callback.message.edit_text(
            f'✅ <b>Оплата записана!</b>\n\n'
            f'🏢 {data.get("client")} — {data.get("amount")} тг\n'
            f'📊 Доходы KZ 2026, строка {row_num}'
        )
        await notify_all(bot, payment_data, row_num)
    except Exception as e:
        logger.error(f'add_payment error: {e}', exc_info=True)
        await callback.message.edit_text(f'❌ Ошибка записи:\n<code>{e}</code>')
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == 'cancel')
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Отменено.')
    await callback.answer()
