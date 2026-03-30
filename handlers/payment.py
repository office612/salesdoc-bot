import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import PaymentStates
from keyboards.payment import (
    package_kb, categories_kb, license_types_kb, periods_kb,
    banks_kb, confirm_kb, skip_kb, months_kb, confirm_price_kb,
    managers_kb, payment_date_kb, calendar_kb, receipt_kb,
)
from services.sheets import add_payment
from services.users import get_user_info, is_accountant, is_manager
from config import (
    CATEGORIES, DIRECTOR_ID, ACCOUNTANT_IDS, MONTH_SHEETS,
    PRICES_NEW, PRICES_OLD, SERVICE_CATS,
)

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


def _build_notify_caption(data: dict, row_num: int) -> str:
    month_num = data.get('month')
    month_name = MONTH_SHEETS.get(int(month_num), '?') if month_num else 'текущий'
    cat = data.get('category', '')
    NEW_CATS = {'new_client', 'nov_vnedrenie', 'nov_integr'}
    header = '🆕 <b>НОВЫЙ КЛИЕНТ!</b>' if cat in NEW_CATS else '💳 <b>Новая оплата!</b>'
    client = data.get('client', data.get('company', '—'))
    qty = data.get('qty', 1)
    price = data.get('price', 0)
    cat_lbl = data.get('category_label', data.get('category_raw', '—'))
    manager = data.get('manager', '—')
    license_type = data.get('license_type', '')
    period = data.get('period', data.get('tariff', ''))
    bank = data.get('bank', '')
    pdate = data.get('payment_date', '')
    fact = data.get('fact_amount', '')
    PERIOD_MONTHS = {
        'Месячный': 1, '3 месячный': 3, '6 месячный': 6,
        '12 месяцев': 12, '10 дней': 0, '20 дней': 0,
    }
    amount = data.get('amount', 0)
    if not amount:
        pm = PERIOD_MONTHS.get(period, 0)
        if pm > 0:
            amount = int(float(qty or 0) * float(price or 0) * pm)
        else:
            amount = int(float(qty or 0) * float(price or 0))
    lines = [
        f'{header}\n',
        f'📅 Месяц: {month_name}',
        f'📆 Дата оплаты: {pdate}' if pdate else '',
        f'🏢 Клиент: {client}',
        f'📦 Статья: {cat_lbl}',
        f'📄 Лицензия: {license_type}' if license_type else '',
        f'🔢 Кол-во: {qty}',
        f'⏱ Тариф: {period}' if period else '',
        f'💵 Цена: {price} тг',
        f'💰 Итого: {amount} тг',
        f'💵 Факт: {fact} тг' if fact else '',
        f'🏦 Банк: {bank}' if bank else '',
        f'👤 Менеджер: {manager}',
        f'📊 Строка {row_num}',
    ]
    return '\n'.join(line for line in lines if line)


def _get_kassa_targets() -> list:
    return [DIRECTOR_ID]


async def _get_kassa_bot():
    kassa_token = os.getenv('KASSA_BOT_TOKEN', '')
    if not kassa_token:
        return None
    return Bot(token=kassa_token)


async def notify_all(bot: Bot, data: dict, row_num: int):
    caption = _build_notify_caption(data, row_num)
    kassa_bot = await _get_kassa_bot()
    if not kassa_bot:
        logger.warning('KASSA_BOT_TOKEN not set')
        return
    try:
        for chat_id in _get_kassa_targets():
            try:
                # Кнопка «Посажено» для записи в таблицу
                planted_kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text='❓ Посажено?',
                        callback_data=f'planted:{row_num}:{data.get("month", 0)}'
                    )
                ]])
                await kassa_bot.send_message(chat_id=chat_id, text=caption, parse_mode='HTML', reply_markup=planted_kb)
            except Exception as e:
                logger.warning(f'kassa notify to {chat_id}: {e}')
    finally:
        await kassa_bot.session.close()


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
async def choose_manager(cb: CallbackQuery, state: FSMContext):
    await state.update_data(manager=cb.data.split(':', 1)[1])
    await cb.message.edit_text('📅 Выберите месяц:', reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)
    await cb.answer()

@router.callback_query(PaymentStates.choose_month, F.data.startswith('month:'))
async def choose_month(cb: CallbackQuery, state: FSMContext):
    await state.update_data(month=int(cb.data.split(':', 1)[1]))
    await cb.message.edit_text('📦 Статья:', reply_markup=categories_kb())
    await state.set_state(PaymentStates.choose_category)
    await cb.answer()

@router.callback_query(PaymentStates.choose_category, F.data == 'cat:more')
async def show_all_categories(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text('📦 Статья:', reply_markup=categories_kb(show_all=True))
    await cb.answer()

@router.callback_query(PaymentStates.choose_category, F.data.startswith('cat:'))
async def choose_category(cb: CallbackQuery, state: FSMContext):
    cat_id = cb.data.split(':', 1)[1]
    cat_label = next((label for key, label in CATEGORIES if key == cat_id), cat_id)
    await state.update_data(category=cat_id, category_label=cat_label)
    if cat_id in SERVICE_CATS:
        await state.update_data(license_type='Услуга', qty=1, period='Услуга')
        await cb.message.edit_text('🏢 Название клиента:')
        await state.set_state(PaymentStates.enter_client)
    else:
        await cb.message.edit_text('📄 Лицензия:', reply_markup=license_types_kb())
        await state.set_state(PaymentStates.choose_license)
    await cb.answer()

@router.callback_query(PaymentStates.choose_license, F.data.startswith('lt:'))
async def choose_license(cb: CallbackQuery, state: FSMContext):
    await state.update_data(license_type=cb.data.split(':', 1)[1])
    await cb.message.edit_text('🏢 Название клиента:')
    await state.set_state(PaymentStates.enter_client)
    await cb.answer()

@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    await state.update_data(client=message.text.strip())
    data = await state.get_data()
    if data.get('category', '') in SERVICE_CATS:
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
async def choose_period(cb: CallbackQuery, state: FSMContext):
    period = cb.data.split(':', 1)[1]
    await state.update_data(period=period)
    data = await state.get_data()
    is_new = data.get('category', '') == 'new_client'
    prices = PRICES_NEW if is_new else PRICES_OLD
    price = prices.get(period, 0)
    if price > 0:
        await cb.message.edit_text('💵 Цена за 1 лицензию:', reply_markup=confirm_price_kb(period, int(data.get('qty', 1)), is_new))
        await state.set_state(PaymentStates.confirm_price)
    else:
        await cb.message.edit_text('💵 Цена за 1 лицензию:')
        await state.set_state(PaymentStates.enter_price)
    await cb.answer()

@router.callback_query(PaymentStates.choose_package, F.data.startswith('pkg:'))
async def choose_package(cb: CallbackQuery, state: FSMContext):
    price = int(cb.data.split(':', 1)[1])
    await state.update_data(price=price, amount=price, fact_amount='')
    await cb.message.edit_text('🏦 Банк оплаты:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)
    await cb.answer()

@router.callback_query(PaymentStates.confirm_price, F.data.startswith('price_ok:'))
async def confirm_price_ok(cb: CallbackQuery, state: FSMContext):
    await state.update_data(price=int(cb.data.split(':', 1)[1]))
    await cb.message.edit_text('🏦 Банк:', reply_markup=banks_kb())
    await state.set_state(PaymentStates.choose_bank)
    await cb.answer()

@router.callback_query(PaymentStates.confirm_price, F.data == 'price_manual')
async def confirm_price_manual(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text('💵 Цена за 1 лицензию:')
    await state.set_state(PaymentStates.enter_price)
    await cb.answer()

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
async def choose_bank(cb: CallbackQuery, state: FSMContext):
    await state.update_data(bank=cb.data.split(':', 1)[1])
    await cb.message.edit_text('💵 Сумма факт (кол. M) — или Пропустить:', reply_markup=skip_kb())
    await state.set_state(PaymentStates.enter_fact)
    await cb.answer()

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
async def skip_fact(cb: CallbackQuery, state: FSMContext):
    await state.update_data(fact_amount='')
    await cb.message.edit_text('📆 Дата оплаты:', reply_markup=payment_date_kb())
    await state.set_state(PaymentStates.choose_payment_date)
    await cb.answer()

@router.callback_query(PaymentStates.choose_payment_date, F.data == 'pdate:cal')
async def open_calendar(cb: CallbackQuery, state: FSMContext):
    from datetime import datetime as dt
    import pytz
    now = dt.now(pytz.timezone('Asia/Almaty'))
    await cb.message.edit_text('📅 Выберите дату:', reply_markup=calendar_kb(now.year, now.month))
    await cb.answer()

@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith('pdate:nav:'))
async def navigate_calendar(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(':')
    y, m, d = int(parts[2]), int(parts[3]), int(parts[4])
    m += d
    if m < 1: m, y = 12, y - 1
    elif m > 12: m, y = 1, y + 1
    await cb.message.edit_reply_markup(reply_markup=calendar_kb(y, m))
    await cb.answer()

@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith('pdate:day:'))
async def pick_calendar_day(cb: CallbackQuery, state: FSMContext):
    await state.update_data(payment_date=cb.data.split(':', 2)[2])
    data = await state.get_data()
    await cb.message.edit_text(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await cb.answer()

@router.callback_query(PaymentStates.choose_payment_date, F.data == 'pdate:noop')
async def noop_handler(cb: CallbackQuery):
    await cb.answer()

@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith('pdate:'))
async def choose_payment_date(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(':', 1)[1]
    if val == 'manual':
        await cb.message.edit_text('✏️ Введите дату ДД.ММ.ГГГГ (например 15.03.2026):')
        await state.set_state(PaymentStates.enter_payment_date)
        await cb.answer()
        return
    await state.update_data(payment_date=val)
    data = await state.get_data()
    await cb.message.edit_text(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)
    await cb.answer()

@router.message(PaymentStates.enter_payment_date)
async def enter_payment_date_manual(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        from datetime import datetime
        date_str = datetime.strptime(text, '%d.%m.%Y').strftime('%d.%m.%Y')
    except ValueError:
        await message.answer('❌ Неверный формат. ДД.ММ.ГГГГ:')
        return
    await state.update_data(payment_date=date_str)
    data = await state.get_data()
    await message.answer(format_summary(data), reply_markup=confirm_kb())
    await state.set_state(PaymentStates.confirm)

@router.callback_query(PaymentStates.confirm, F.data == 'pay_confirm')
async def confirm_payment_handler(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pd = {
        'company': data.get('client', ''), 'client': data.get('client', ''),
        'category': data.get('category', ''), 'category_raw': data.get('category', ''),
        'category_label': data.get('category_label', ''),
        'license_type': data.get('license_type', ''),
        'license_qty': data.get('qty', 0), 'qty': data.get('qty', 0),
        'manager': data.get('manager', ''),
        'tariff': data.get('period', ''), 'period': data.get('period', ''),
        'price': data.get('price', 0), 'amount': data.get('amount', 0),
        'bank': data.get('bank', ''), 'fact_amount': data.get('fact_amount', ''),
        'month': data.get('month'), 'start_month': data.get('start_month', ''),
        'activation_date': data.get('activation_date', ''),
        'act_price': data.get('act_price', ''), 'payment_date': data.get('payment_date', ''),
    }
    try:
        row_num = await add_payment(pd)
        mn = data.get('month')
        month_name = MONTH_SHEETS.get(int(mn), '?') if mn else 'текущий'
        await cb.message.edit_text(
            f'✅ <b>Оплата записана!</b>\n\n'
            f'📅 {month_name}\n'
            f'🏢 {data.get("client")} | {data.get("qty")} x {data.get("price")} тг\n'
            f'📊 Доходы KZ 2026, строка {row_num}')
        await state.update_data(saved_row=row_num, saved_month=int(mn), payment_data_cache=pd)
        await cb.message.answer('📎 Прикрепите скриншот оплаты (фото или файл)\nили нажмите Пропустить:', reply_markup=receipt_kb())
        await state.set_state(PaymentStates.upload_receipt)
    except Exception as e:
        logger.error(f'add_payment error: {e}', exc_info=True)
        await cb.message.edit_text(f'❌ Ошибка:\n<code>{e}</code>')
        await state.clear()
    await cb.answer()

@router.message(PaymentStates.upload_receipt, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    row_num = data.get('saved_row', '?')
    payment_data = data.get('payment_data_cache', data)
    photo = message.photo[-1]
    caption = _build_notify_caption(payment_data, row_num)
    try:
        file_info = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download_file(file_info.file_path)
        kassa_bot = await _get_kassa_bot()
        if kassa_bot:
            try:
                from aiogram.types import BufferedInputFile
                inp = BufferedInputFile(file_bytes.read(), filename=f'receipt_{row_num}.jpg')
                for chat_id in _get_kassa_targets():
                    try:
                        planted_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❓ Посажено?', callback_data=f'planted:{row_num}:{payment_data.get("month", 0)}')]])
                        await kassa_bot.send_photo(chat_id=chat_id, photo=inp, caption=caption, parse_mode='HTML', reply_markup=planted_kb)
                    except Exception as e:
                        logger.warning(f'kassa photo to {chat_id}: {e}')
            finally:
                await kassa_bot.session.close()
            await message.answer('✅ Скрин оплаты отправлен!')
        else:
            await message.answer('⚠️ KASSA_BOT_TOKEN не настроен.')
    except Exception as e:
        logger.error(f'Receipt photo error: {e}', exc_info=True)
        await message.answer(f'⚠️ Не удалось отправить скрин: {e}')
    await state.clear()

@router.message(PaymentStates.upload_receipt, F.document)
async def handle_receipt_document(message: Message, state: FSMContext):
    data = await state.get_data()
    row_num = data.get('saved_row', '?')
    payment_data = data.get('payment_data_cache', data)
    doc = message.document
    caption = _build_notify_caption(payment_data, row_num)
    try:
        file_info = await message.bot.get_file(doc.file_id)
        file_bytes = await message.bot.download_file(file_info.file_path)
        kassa_bot = await _get_kassa_bot()
        if kassa_bot:
            try:
                from aiogram.types import BufferedInputFile
                inp = BufferedInputFile(file_bytes.read(), filename=doc.file_name or f'receipt_{row_num}')
                for chat_id in _get_kassa_targets():
                    try:
                        planted_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❓ Посажено?', callback_data=f'planted:{row_num}:{payment_data.get("month", 0)}')]])
                        await kassa_bot.send_document(chat_id=chat_id, document=inp, caption=caption, parse_mode='HTML', reply_markup=planted_kb)
                    except Exception as e:
                        logger.warning(f'kassa doc to {chat_id}: {e}')
            finally:
                await kassa_bot.session.close()
            await message.answer('✅ Файл оплаты отправлен!')
        else:
            await message.answer('⚠️ KASSA_BOT_TOKEN не настроен.')
    except Exception as e:
        logger.error(f'Receipt doc error: {e}', exc_info=True)
        await message.answer(f'⚠️ Не удалось отправить файл: {e}')
    await state.clear()

@router.callback_query(PaymentStates.upload_receipt, F.data == 'skip_receipt')
async def skip_receipt(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    row_num = data.get('saved_row', '?')
    payment_data = data.get('payment_data_cache', data)
    await notify_all(cb.bot, payment_data, row_num)
    await cb.message.edit_text('▶️ Скрин пропущен. Оплата записана.')
    await state.clear()
    await cb.answer()

@router.callback_query(PaymentStates.confirm, F.data == 'pay_cancel')
async def cancel_payment(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text('❌ Отменено.')
    await cb.answer()
