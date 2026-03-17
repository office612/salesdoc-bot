import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import PaymentStates
from keyboards.payment import (
    categories_kb, license_types_kb, periods_kb,
    banks_kb, confirm_kb, skip_kb, months_kb
)
from services.sheets import add_payment
from services.users import get_user_info
from config import CATEGORIES, DIRECTOR_ID, ACCOUNTANT_IDS, MONTH_SHEETS

logger = logging.getLogger(__name__)
router = Router()


def format_summary(data: dict) -> str:
    month_num = data.get('month')
    month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
    fact = data.get('fact_amount', '')
    fact_str = f'\n💵 Сумма факт: <b>{fact}</b>' if fact else ''
    return (
        f'📋 <b>Проверка:</b>\n\n'
        f'📅 Месяц: <b>{month_name}</b>\n'
        f'📦 Статья: <b>{data.get("category", "—")}</b>\n'
        f'📄 Лицензия: <b>{data.get("license_type", "—")}</b>\n'
        f'🏢 Клиент: <b>{data.get("client", "—")}</b>\n'
        f'🔢 Кол-во: <b>{data.get("qty", "—")}</b>\n'
        f'⏱ Тариф: <b>{data.get("period", "—")}</b>\n'
        f'💵 Цена: <b>{data.get("price", "—")}</b>\n'
        f'💰 Сумма: <b>{data.get("amount", "—")}</b>\n'
        f'🏦 Банк: <b>{data.get("bank", "—")}</b>\n'
        f'👤 Менеджер: <b>{data.get("manager", "—")}</b>'
        f'{fact_str}'
    )


async def notify_all(bot, data: dict, row_num: int):
    month_num = data.get('month')
    month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
    fact = data.get('fact_amount', '')
    fact_str = f'\n💵 Факт: <b>{fact}</b>' if fact else ''
    text = (
        f'💰 <b>Новая оплата!</b>\n\n'
        f'📅 Месяц: <b>{month_name}</b>\n'
        f'🏢 <b>{data.get("client", "—")}</b>\n'
        f'💰 {data.get("qty", "—")} × {data.get("price", "—")} тг — {data.get("bank", "—")}\n'
        f'📦 {data.get("category", "—")} | {data.get("license_type", "—")}\n'
        f'👤 {data.get("manager", "—")}'
        f'{fact_str}\n'
        f'📊 Строка {row_num}'
    )
    try:
        await bot.send_message(DIRECTOR_ID, text)
    except Exception as e:
        logger.warning(f'notify director: {e}')

    # Отправка в @kassasdkzbot
    kassa_token = os.getenv("KASSA_BOT_TOKEN", "")
    if kassa_token:
        try:
            kassa_bot = Bot(token=kassa_token)
            await kassa_bot.send_message(DIRECTOR_ID, text, parse_mode="HTML")
            await kassa_bot.session.close()
        except Exception as e:
            logger.warning(f'kassa_bot notify failed: {e}')


@router.message(F.text == '💳 Внести оплату')
async def start_payment(message: Message, state: FSMContext):
    await state.clear()
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer('Не авторизован. /start')
        return
    await state.update_data(manager=user['name'])
    await message.answer('📅 Выберите месяц:', reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)


@router.callback_query(PaymentStates.choose_month, F.data.startswith('month:'))
async def choose_month(callback: CallbackQuery, state: FSMContext):
    month = int(callback.data.split(':', 1)[1])
    await state.update_data(month=month)
    await callback.message.edit_text('📦 Статья:', reply_markup=categories_kb())
    await state.set_state(PaymentStates.choose_category)
    await callback.answer()


@router.callback_query(PaymentStates.choose_category, F.data.startswith('cat:'))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(':', 1)[1]
    cat_label = next((label for key, label in CATEGORIES if key == cat_id), cat_id)
    await state.update_data(category=cat_label)
    await callback.message.edit_text('📄 Лицензия:', reply_markup=license_types_kb())
    await state.set_state(PaymentStates.choose_license)
    await callback.answer()


@router.callback_query(PaymentStates.choose_license, F.data.startswith('lt:'))
async def choose_license(callback: CallbackQuery, state: FSMContext):
    lt = callback.data.split(':', 1)[1]
    await state.update_data(license_type=lt)
    await callback.message.edit_text('🏢 Название клиента:')
    await state.set_state(PaymentStates.enter_client)
    await callback.answer()


@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    await message.answer('🔢 Кол-во лицензий:')
    await state.set_state(PaymentStates.enter_qty)


@router.message(PaymentStates.enter_qty)
async def enter_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except ValueError:
        await message.answer('❌ Целое число, например: 1')
        return
    await state.update_data(qty=qty)
    await message.answer('⏱ Тариф:', reply_markup=periods_kb())
    await state.set_state(PaymentStates.choose_period)


@router.callback_query(PaymentStates.choose_period, F.data.startswith('period:'))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(':', 1)[1]
    await state.update_data(period=period)
    await callback.message.edit_text('💵 Цена за 1 лицензию:')
    await state.set_state(PaymentStates.enter_price)
    await callback.answer()


@router.message(PaymentStates.enter_price)
async def enter_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(' ', '').replace(',', '.'))
    except ValueError:
        await message.answer('❌ Число, например: 5000')
        return
    await state.update_data(price=price)
    await message.answer('🏦 Банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)



@router.callback_query(PaymentStates.choose_bank, F.data.startswith('bank:'))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(':', 1)[1]
    await state.update_data(bank=bank)
    await callback.message.edit_text(
        '💵 Сумма факт (кол. M) — или Пропустить:',
        reply_markup=skip_kb()
    )
    await state.set_state(PaymentStates.enter_fact)
    await callback.answer()


@router.message(PaymentStates.enter_fact)
async def enter_fact(message: Message, state: FSMContext):
    try:
        fact = float(message.text.strip().replace(' ', '').replace(',', '.'))
    except ValueError:
        await message.answer('❌ Число или Пропустить')
        return
    await state.update_data(fact_amount=fact)
    data = await state.get_data()
    await message.answer(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)


@router.callback_query(PaymentStates.enter_fact, F.data == 'skip')
async def skip_fact(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fact_amount='')
    data = await state.get_data()
    await callback.message.edit_text(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await callback.answer()


@router.callback_query(PaymentStates.confirm, F.data == 'pay_confirm')
async def confirm_payment_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_data = {
        'company':      data.get('client', ''),
        'category_raw': data.get('category', ''),
        'license_type': data.get('license_type', ''),
        'license_qty':  data.get('qty', 0),
        'manager':      data.get('manager', ''),
        'tariff':       data.get('period', ''),
        'price':        data.get('price', 0),
        'bank':         data.get('bank', ''),
        'fact_amount':  data.get('fact_amount', ''),
        'month':        data.get('month'),
    }
    try:
        row_num = add_payment(payment_data)
        month_num = data.get('month')
        month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
        await callback.message.edit_text(
            f'✅ <b>Оплата записана!</b>\n\n'
            f'📅 {month_name}\n'
            f'🏢 {data.get("client")} | {data.get("qty")} × {data.get("price")} тг\n'
            f'📊 Доходы KZ 2026, строка {row_num}'
        )
        await notify_all(callback.bot, data, row_num)
    except Exception as e:
        logger.error(f'add_payment error: {e}', exc_info=True)
        await callback.message.edit_text(f'❌ Ошибка:\n<code>{e}</code>')
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == 'cancel')
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Отменено.')
    await callback.answer()



