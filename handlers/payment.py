import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import PaymentStates
from keyboards.payment import (
    categories_kb, license_types_kb, periods_kb,
    banks_kb, confirm_kb, skip_kb, months_kb,
    confirm_price_kb, start_month_kb, activation_kb, act_period_kb,
)
from services.sheets import add_payment
from services.users import get_user_info
from config import (
    CATEGORIES, DIRECTOR_ID, ACCOUNTANT_IDS, MONTH_SHEETS,
    PRICES_NEW, PRICES_OLD, NEW_CLIENT_DATE,
)

logger = logging.getLogger(__name__)
router = Router()

# Категории для которых спрашиваем начало периода
ABON_CATS = {'abon_plata', 'dop_lic', 'balans'}
# Категории новых клиентов
NEW_CLIENT_CATS = {'new_client', 'nov_vnedrenie', 'nov_integr'}


def format_summary(data: dict) -> str:
    month_num = data.get('month')
    month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
    fact = data.get('fact_amount', '')
    fact_str = f'\n💵 Факт: <b>{fact}</b>' if fact else ''
    start_m = data.get('start_month')
    start_str = f'\n📆 Начало: <b>{MONTH_SHEETS.get(int(start_m), "?")}</b>' if start_m else ''
    act = data.get('activation_date', '')
    act_str = f'\n🟢 Активация: <b>{act}</b>' if act else ''
    act_p = data.get('act_period_label', '')
    act_p_str = f'\n⏱ Период акт.: <b>{act_p}</b>' if act_p else ''
    return (
        f'📋 <b>Проверка:</b>\n\n'
        f'📅 Месяц: <b>{month_name}</b>\n'
        f'📦 Статья: <b>{data.get("category_label", "—")}</b>\n'
        f'📄 Лицензия: <b>{data.get("license_type", "—")}</b>\n'
        f'🏢 Клиент: <b>{data.get("client", "—")}</b>\n'
        f'🔢 Кол-во: <b>{data.get("qty", "—")}</b>\n'
        f'⏱ Тариф: <b>{data.get("period", "—")}</b>\n'
        f'💰 Цена: <b>{data.get("price", "—")} тг</b>\n'
        f'💴 Сумма: <b>{data.get("amount", "—")} тг</b>\n'
        f'🏦 Банк: <b>{data.get("bank", "—")}</b>'
        f'{fact_str}{start_str}{act_str}{act_p_str}'
    )


async def notify_all(bot, data: dict, row_num: int):
    month_num = data.get('month')
    month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
    text = (
        f'💳 <b>Новая оплата!</b>\n\n'
        f'📅 {month_name}\n'
        f'🏢 {data.get("client")} | {data.get("qty")} x {data.get("price")} тг\n'
        f'📦 {data.get("category_label", "—")}\n'
        f'💴 Итого: {data.get("amount")} тг\n'
        f'👤 {data.get("manager", "—")}\n'
        f'📊 Строка {row_num}'
    )
    for uid in [DIRECTOR_ID] + ACCOUNTANT_IDS:
        try:
            await bot.send_message(uid, text, parse_mode='HTML')
        except Exception as e:
            logger.warning(f'notify {uid}: {e}')


# ══════════════════════════════════════════════
# STEP 1: Выбор месяца
# ══════════════════════════════════════════════
@router.message(F.text == '💳 Внести оплату')
async def start_payment(message: Message, state: FSMContext):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer('❌ Нет доступа')
        return
    await state.update_data(manager=user['name'])
    await message.answer('📅 Выбери месяц:', reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)


@router.callback_query(PaymentStates.choose_month, F.data.startswith('month:'))
async def choose_month(callback: CallbackQuery, state: FSMContext):
    month = callback.data.split(':', 1)[1]
    await state.update_data(month=month)
    await callback.message.edit_text('📦 Статья:', reply_markup=categories_kb())
    await state.set_state(PaymentStates.choose_category)
    await callback.answer()


# ══════════════════════════════════════════════
# STEP 2: Статья и лицензия
# ══════════════════════════════════════════════
@router.callback_query(PaymentStates.choose_category, F.data.startswith('cat:'))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.split(':', 1)[1]
    cat_label = next((lbl for k, lbl in CATEGORIES if k == cat_key), cat_key)
    await state.update_data(category=cat_key, category_label=cat_label)
    await callback.message.edit_text('📄 Тип лицензии:', reply_markup=license_types_kb())
    await state.set_state(PaymentStates.choose_license)
    await callback.answer()


@router.callback_query(PaymentStates.choose_license, F.data.startswith('lt:'))
async def choose_license(callback: CallbackQuery, state: FSMContext):
    lt = callback.data.split(':', 1)[1]
    await state.update_data(license_type=lt)
    await callback.message.edit_text('🏢 Название клиента:')
    await state.set_state(PaymentStates.enter_client)
    await callback.answer()


# ══════════════════════════════════════════════
# STEP 3: Клиент, кол-во, тариф
# ══════════════════════════════════════════════
@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    data = await state.get_data()
    cat = data.get('category', '')
    SERVICE_CATS = {'usluga', 'nov_vnedrenie', 'nov_integr', 'nakladnaya', 'oplata_dolga'}
    if cat in SERVICE_CATS:
        await state.update_data(qty=1, license_type='Услуга')
        await message.answer('⏱ Тариф:', reply_markup=periods_kb())
        await state.set_state(PaymentStates.choose_period)
    else:
        await message.answer('U0001f522 Кол-во лицензий:')
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


# ══════════════════════════════════════════════
# STEP 4: Тариф -> Авто-цена
# ══════════════════════════════════════════════
@router.callback_query(PaymentStates.choose_period, F.data.startswith('period:'))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(':', 1)[1]
    await state.update_data(period=period)
    data = await state.get_data()
    qty = data.get('qty', 1)
    month_num = int(data.get('month', datetime.now().month))
    is_new = month_num >= 3  # с марта 2026 — новые цены
    await state.update_data(is_new_client=is_new)
    if period in PRICES_NEW or period in PRICES_OLD:
        await callback.message.edit_text(
            f'💰 Авто-цена для тарифа <b>{period}</b>:',
            reply_markup=confirm_price_kb(period, qty, is_new),
            parse_mode='HTML'
        )
        await state.set_state(PaymentStates.confirm_price)
    else:
        await callback.message.edit_text('💵 Введи цену за 1 лицензию:')
        await state.set_state(PaymentStates.enter_price)
    await callback.answer()


@router.callback_query(PaymentStates.confirm_price, F.data.startswith('price_ok:'))
async def price_ok(callback: CallbackQuery, state: FSMContext):
    price = int(callback.data.split(':', 1)[1])
    data = await state.get_data()
    amount = price * data.get('qty', 1)
    await state.update_data(price=price, amount=amount)
    await callback.message.edit_text(
        f'💴 Итого: <b>{amount:,} тг</b>\nФактическая сумма оплаты (или Пропустить):',
        reply_markup=skip_kb(), parse_mode='HTML'
    )
    await state.set_state(PaymentStates.enter_amount)
    await callback.answer()


@router.callback_query(PaymentStates.confirm_price, F.data == 'price_manual')
async def price_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('💵 Введи цену за 1 лицензию:')
    await state.set_state(PaymentStates.enter_price)
    await callback.answer()


@router.message(PaymentStates.enter_price)
async def enter_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(' ', '').replace(',', ''))
    except ValueError:
        await message.answer('❌ Введи число, например: 7000')
        return
    data = await state.get_data()
    amount = price * data.get('qty', 1)
    await state.update_data(price=price, amount=amount)
    await message.answer(
        f'💴 Итого: <b>{amount:,} тг</b>\nФактическая сумма (или Пропустить):',
        reply_markup=skip_kb(), parse_mode='HTML'
    )
    await state.set_state(PaymentStates.enter_amount)


# ══════════════════════════════════════════════
# STEP 5: Сумма, банк, факт
# ══════════════════════════════════════════════
@router.message(PaymentStates.enter_amount)
async def enter_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip().replace(' ', '').replace(',', ''))
    except ValueError:
        await message.answer('❌ Введи число')
        return
    await state.update_data(amount=amount)
    await message.answer('🏦 Банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)


@router.callback_query(PaymentStates.enter_amount, F.data == 'skip')
async def skip_amount(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('🏦 Банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)
    await callback.answer()


@router.callback_query(PaymentStates.choose_bank, F.data.startswith('bank:'))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(':', 1)[1]
    await state.update_data(bank=bank)
    await callback.message.edit_text('💵 Сумма факт (или Пропустить):', reply_markup=skip_kb())
    await state.set_state(PaymentStates.enter_fact)
    await callback.answer()


@router.message(PaymentStates.enter_fact)
async def enter_fact(message: Message, state: FSMContext):
    await state.update_data(fact_amount=message.text.strip())
    await _ask_start_month(message, await state.get_data(), state)


@router.callback_query(PaymentStates.enter_fact, F.data == 'skip')
async def skip_fact(callback: CallbackQuery, state: FSMContext):
    await _ask_start_month(callback.message, await state.get_data(), state)
    await callback.answer()


# ══════════════════════════════════════════════
# STEP 6: С какого месяца / Активация
# ══════════════════════════════════════════════
async def _ask_start_month(message, data: dict, state: FSMContext):
    cat = data.get('category', '')
    if cat in ABON_CATS:
        await message.answer('📆 С какого месяца начинается эта оплата?', reply_markup=start_month_kb())
        await state.set_state(PaymentStates.choose_start_month)
    elif cat in NEW_CLIENT_CATS:
        await message.answer('🟢 Клиент активирован?', reply_markup=activation_kb())
        await state.set_state(PaymentStates.choose_activation)
    else:
        await _show_confirm(message, data, state)


@router.callback_query(PaymentStates.choose_start_month, F.data.startswith('start_month:'))
async def choose_start_month(callback: CallbackQuery, state: FSMContext):
    month_num = callback.data.split(':', 1)[1]
    await state.update_data(start_month=month_num)
    await _show_confirm(callback.message, await state.get_data(), state)
    await callback.answer()


# ══════════════════════════════════════════════
# STEP 7: Активация нового клиента
# ══════════════════════════════════════════════
@router.callback_query(PaymentStates.choose_activation, F.data.startswith('activated:'))
async def choose_activation(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split(':', 1)[1]
    if status == 'yes':
        await callback.message.edit_text('⏱ Период активации в этом месяце:', reply_markup=act_period_kb())
        await state.set_state(PaymentStates.choose_act_period)
    else:
        await state.update_data(activation_date='', act_price=0, act_period_label='Не активирован')
        await _show_confirm(callback.message, await state.get_data(), state)
    await callback.answer()


@router.callback_query(PaymentStates.choose_act_period, F.data.startswith('act_period:'))
async def choose_act_period(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(':')
    days = parts[1]
    price_per_lic = int(parts[2])
    label_map = {'10': '10 дней', '20': '20 дней', '30': 'Полный месяц'}
    label = label_map.get(days, days + ' дней')
    today = datetime.now().strftime('%d.%m.%Y')
    await state.update_data(activation_date=today, act_price=price_per_lic, act_period_label=label)
    await _show_confirm(callback.message, await state.get_data(), state)
    await callback.answer()


# ══════════════════════════════════════════════
# STEP 8: Подтверждение и запись
# ══════════════════════════════════════════════
async def _show_confirm(message, data: dict, state: FSMContext):
    await message.answer(format_summary(data), reply_markup=confirm_kb(), parse_mode='HTML')
    await state.set_state(PaymentStates.confirm)


@router.callback_query(PaymentStates.confirm, F.data == 'confirm')
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        row_num = await add_payment(data)
        month_num = data.get('month')
        month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
        await callback.message.edit_text(
            f'✅ <b>Оплата записана!</b>\n\n'
            f'📅 {month_name}\n'
            f'🏢 {data.get("client")} | {data.get("qty")} x {data.get("price")} тг\n'
            f'📊 Строка {row_num}',
            parse_mode='HTML'
        )
        await notify_all(callback.bot, data, row_num)
    except Exception as e:
        logger.error(f'add_payment error: {e}', exc_info=True)
        await callback.message.edit_text(f'❌ Ошибка:\n<code>{e}</code>', parse_mode='HTML')
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == 'cancel')
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text('❌ Отменено.')
    await callback.answer()
