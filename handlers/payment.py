import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import PaymentStates
from keyboards.payment import (
    package_kb, categories_kb, license_types_kb, periods_kb,
    banks_kb, confirm_kb, skip_kb, months_kb, confirm_price_kb,
    managers_kb, payment_date_kb, calendar_kb
)
from services.sheets import add_payment
from services.users import get_user_info, is_accountant, is_manager
from config import CATEGORIES, DIRECTOR_ID, ACCOUNTANT_IDS, MONTH_SHEETS, PRICES_NEW, PRICES_OLD, SERVICE_CATS

logger = logging.getLogger(__name__)
router = Router()


def format_summary(data: dict) -> str:
    month_num = data.get('month')
    month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
    fact = data.get('fact_amount', '')
    fact_str = f'\n💵 Сумма факт: <b>{fact}</b>' if fact else ''
    pdate = data.get('payment_date', 'сегодня')
    return (
        f'📋 <b>Проверка:</b>\n\n'
        f'📅 Месяц: <b>{month_name}</b>\n'
        f'📆 Дата оплаты: <b>{pdate}</b>\n'
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
    cat = data.get('category', '')
    NEW_CATS = {'new_client', 'nov_vnedrenie', 'nov_integr'}
    if cat in NEW_CATS:
        header = '🆕 <b>НОВЫЙ КЛИЕНТ!</b>'
    else:
        header = '💳 <b>Новая оплата!</b>'
    client = data.get('client', data.get('company', '—'))
    qty = data.get('qty', 1)
    price = data.get('price', 0)
    amount = data.get('amount', 0) or int(float(qty or 0) * float(price or 0))
    cat_lbl = data.get('category_label', data.get('category_raw', '—'))
    manager = data.get('manager', '—')
    text = (
        f'{header}\n\n'
        f'📅 {month_name}\n'
        f'🏢 {client} | {qty} x {price} тг\n'
        f'📦 {cat_lbl}\n'
        f'💴 Итого: {amount} тг\n'
        f'👤 {manager}\n'
        f'📊 Строка {row_num}'
    )
    kassa_token = os.getenv('KASSA_BOT_TOKEN', '')
    kassa_chat = os.getenv('ACCOUNTANT_CHAT_ID', '')
    if kassa_token and kassa_chat:
        try:
            kassa_bot = Bot(token=kassa_token)
            await kassa_bot.send_message(DIRECTOR_ID, text, parse_mode='HTML')
            await kassa_bot.send_message(int(kassa_chat), text, parse_mode='HTML')
            await kassa_bot.session.close()
            logger.info(f'Kassa notifications sent')
        except Exception as e:
            logger.warning(f'kassa notify error: {e}')


@router.message(F.text == '💳 Внести оплату')
async def start_payment(message: Message, state: FSMContext):
    await state.clear()
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer('Не авторизован. /start')
        return
    if is_accountant(user) and not is_manager(user):
        await message.answer('👤 За какого менеджера садите оплату?', reply_markup=managers_kb())
        await state.set_state(PaymentStates.choose_manager)
    else:
        await state.update_data(manager=user['name'])
        await message.answer('📅 Выберите месяц:', reply_markup=months_kb())
        await state.set_state(PaymentStates.choose_month)


@router.callback_query(PaymentStates.choose_manager, F.data.startswith('mgr:'))
async def choose_manager(callback: CallbackQuery, state: FSMContext):
    manager_name = callback.data.split(':', 1)[1]
    await state.update_data(manager=manager_name)
    await callback.message.edit_text('📅 Выберите месяц:', reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)
    await callback.answer()


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
    await state.update_data(category=cat_id, category_label=cat_label)
    if cat_id in SERVICE_CATS:
        await state.update_data(license_type='Услуга', qty=1, period='Услуга')
        await callback.message.edit_text('🏢 Название клиента:')
        await state.set_state(PaymentStates.enter_client)
    else:
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
    data = await state.get_data()
    cat = data.get('category', '')
    if cat in SERVICE_CATS:
        await message.answer('📦 Выбери пакет:', reply_markup=package_kb())
        await state.set_state(PaymentStates.choose_package)
    else:
        await message.answer('🔢 Кол-во лицензий:')
        await state.set_state(PaymentStates.enter_qty)


@router.message(PaymentStates.enter_qty)
async def enter_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except ValueError:
        await message.answer('❌ Целое число')
        return
    await state.update_data(qty=qty)
    await message.answer('⏱ Тариф:', reply_markup=periods_kb())
    await state.set_state(PaymentStates.choose_period)


@router.callback_query(PaymentStates.choose_period, F.data.startswith('period:'))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(':', 1)[1]
    await state.update_data(period=period)
    data = await state.get_data()
    qty = int(data.get('qty', 1))
    cat = data.get('category', '')
    is_new = cat == 'new_client'
    prices = PRICES_NEW if is_new else PRICES_OLD
    price = prices.get(period, 0)
    if price > 0:
        await callback.message.edit_text('💵 Цена за 1 лицензию:', reply_markup=confirm_price_kb(period, qty, is_new))
        await state.set_state(PaymentStates.confirm_price)
    else:
        await callback.message.edit_text('💵 Цена за 1 лицензию:')
        await state.set_state(PaymentStates.enter_price)
    await callback.answer()


@router.callback_query(PaymentStates.choose_package, F.data.startswith('pkg:'))
async def choose_package(callback: CallbackQuery, state: FSMContext):
    price = int(callback.data.split(':', 1)[1])
    await state.update_data(price=price, amount=price, fact_amount='')
    await callback.message.edit_text('🏦 Банк оплаты:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)
    await callback.answer()


@router.callback_query(PaymentStates.confirm_price, F.data.startswith('price_ok:'))
async def confirm_price_ok(callback: CallbackQuery, state: FSMContext):
    price = int(callback.data.split(':', 1)[1])
    await state.update_data(price=price)
    await callback.message.edit_text('🏦 Банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)
    await callback.answer()


@router.callback_query(PaymentStates.confirm_price, F.data == 'price_manual')
async def confirm_price_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('💵 Цена за 1 лицензию:')
    await state.set_state(PaymentStates.enter_price)
    await callback.answer()


@router.message(PaymentStates.enter_price)
async def enter_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(' ', '').replace(',', '.'))
    except ValueError:
        await message.answer('❌ Число')
        return
    await state.update_data(price=price)
    await message.answer('🏦 Банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)


@router.callback_query(PaymentStates.choose_bank, F.data.startswith('bank:'))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(':', 1)[1]
    await state.update_data(bank=bank)
    await callback.message.edit_text('💵 Сумма факт (кол. M) — или Пропустить:', reply_markup=skip_kb())
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
    await message.answer('📆 Дата оплаты:', reply_markup=payment_date_kb())
    await state.set_state(PaymentStates.choose_payment_date)


@router.callback_query(PaymentStates.enter_fact, F.data == 'skip')
async def skip_fact(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fact_amount='')
    await callback.message.edit_text('📆 Дата оплаты:', reply_markup=payment_date_kb())
    await state.set_state(PaymentStates.choose_payment_date)
    await callback.answer()


# ── Календарь: открыть ──
@router.callback_query(PaymentStates.choose_payment_date, F.data == 'pdate:cal')
async def open_calendar(callback: CallbackQuery, state: FSMContext):
    from datetime import datetime as dt
    import pytz
    tz = pytz.timezone('Asia/Almaty')
    now = dt.now(tz)
    await callback.message.edit_text(
        '📅 Выберите дату:',
        reply_markup=calendar_kb(now.year, now.month)
    )
    await callback.answer()


# ── Календарь: навигация ◀ ▶ ──
@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith('pdate:nav:'))
async def navigate_calendar(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(':')
    year = int(parts[2])
    month = int(parts[3])
    delta = int(parts[4])
    month += delta
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    await callback.message.edit_reply_markup(
        reply_markup=calendar_kb(year, month)
    )
    await callback.answer()


# ── Календарь: выбор дня ──
@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith('pdate:day:'))
async def pick_calendar_day(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(':', 2)[2]
    await state.update_data(payment_date=date_str)
    data = await state.get_data()
    await callback.message.edit_text(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await callback.answer()


# ── Календарь: пустые кнопки (заголовок, дни недели) ──
@router.callback_query(PaymentStates.choose_payment_date, F.data == 'pdate:noop')
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


# ── Сегодня / Вчера / Ввести вручную ──
@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith('pdate:'))
async def choose_payment_date(callback: CallbackQuery, state: FSMContext):
    val = callback.data.split(':', 1)[1]
    if val == 'manual':
        await callback.message.edit_text('✏️ Введите дату в формате ДД.ММ.ГГГГ (например 15.03.2026):')
        await state.set_state(PaymentStates.enter_payment_date)
        await callback.answer()
        return
    await state.update_data(payment_date=val)
    data = await state.get_data()
    await callback.message.edit_text(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await callback.answer()


@router.message(PaymentStates.enter_payment_date)
async def enter_payment_date_manual(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        from datetime import datetime
        parsed = datetime.strptime(text, '%d.%m.%Y')
        date_str = parsed.strftime('%d.%m.%Y')
    except ValueError:
        await message.answer('❌ Неверный формат. Введите ДД.ММ.ГГГГ (например 15.03.2026):')
        return
    await state.update_data(payment_date=date_str)
    data = await state.get_data()
    await message.answer(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)


@router.callback_query(PaymentStates.confirm, F.data == 'pay_confirm')
async def confirm_payment_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_data = {
        'company': data.get('client', ''),
        'client': data.get('client', ''),
        'category': data.get('category', ''),
        'category_raw': data.get('category', ''),
        'category_label': data.get('category_label', ''),
        'license_type': data.get('license_type', ''),
        'license_qty': data.get('qty', 0),
        'qty': data.get('qty', 0),
        'manager': data.get('manager', ''),
        'tariff': data.get('period', ''),
        'period': data.get('period', ''),
        'price': data.get('price', 0),
        'amount': data.get('amount', 0),
        'bank': data.get('bank', ''),
        'fact_amount': data.get('fact_amount', ''),
        'month': data.get('month'),
        'start_month': data.get('start_month', ''),
        'activation_date': data.get('activation_date', ''),
        'act_price': data.get('act_price', ''),
        'payment_date': data.get('payment_date', ''),
    }
    try:
        row_num = await add_payment(payment_data)
        month_num = data.get('month')
        month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
        await callback.message.edit_text(
            f'✅ <b>Оплата записана!</b>\n\n'
            f'📅 {month_name}\n'
            f'🏢 {data.get("client")} | {data.get("qty")} x {data.get("price")} тг\n'
            f'📊 Доходы KZ 2026, строка {row_num}'
        )
        await notify_all(callback.bot, payment_data, row_num)
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
