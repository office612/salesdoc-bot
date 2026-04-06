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
    back_button, service_categories_kb, calendar_kb,
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

@router.message(F.text == "💳 Внести оплату")
async def start_payment_text(message: Message, state: FSMContext):
    """Обработчик текстовой кнопки Внести оплату"""
    await state.clear()
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Вы не авторизованы. Нажмите /start")
        return
    await state.update_data(manager=user["name"])
    await message.answer("Выберите месяц:", reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)


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


# ═══════════════════════════════════════════════════════════════════════════════
# ВВОД КЛИЕНТА → РАЗВЕТВЛЕНИЕ ПО КАТЕГОРИИ
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(PaymentStates.enter_client)
async def enter_client(message: Message, state: FSMContext):
    client = message.text.strip()
    await state.update_data(client=client)
    data = await state.get_data()
    cat_key = data.get("category_key", "")

    # РУЧНОЙ ВВОД СУММЫ (наклодная, долг, доработка, 2гис)
    if cat_key in MANUAL_AMOUNT_CATS:
        await message.answer(
            f"Клиент: {client}\nВведите сумму:",
            reply_markup=manual_amount_kb()
        )
        await state.set_state(PaymentStates.enter_manual_amount)
        return

    # БОТЫ (телеграм боты, бот отчет, бот заказ) → период → сумма вручную
    if cat_key in BOT_CATS:
        await message.answer(
            f"Клиент: {client}\nВыберите период:",
            reply_markup=bot_periods_kb()
        )
        await state.set_state(PaymentStates.choose_bot_period)
        return

    # УСЛУГИ С ПАКЕТАМИ (внедрение, интеграция)
    if cat_key in SERVICE_CATS:
        await message.answer(
            f"Клиент: {client}\nВыберите пакет:",
            reply_markup=package_kb()
        )
        await state.set_state(PaymentStates.choose_package)
        return

    # ЛИЦЕНЗИИ → ввод количества
    await message.answer(f"Клиент: {client}\nВведите количество лицензий:")
    await state.set_state(PaymentStates.enter_qty)


# ═══════════════════════════════════════════════════════════════════════════════
# РУЧНОЙ ВВОД СУММЫ (наклодная, долг и др.)
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(PaymentStates.enter_manual_amount)
async def enter_manual_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("Введите число. Попробуйте ещё раз:")
        return

    await state.update_data(amount=amount, price=amount)
    data = await state.get_data()
    await message.answer(
        f"Клиент: {data['client']}\nСумма: {amount} тг\nВыберите банк:",
        reply_markup=banks_kb("back:manual_amount")
    )
    await state.set_state(PaymentStates.choose_bank)


# ═══════════════════════════════════════════════════════════════════════════════
# БОТЫ: ПЕРИОД → СУММА
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(PaymentStates.choose_bot_period, F.data.startswith("botper:"))
async def choose_bot_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]
    await state.update_data(period=period)
    await callback.message.edit_text(
        f"Период: {period}\nВведите сумму:"
    )
    await state.set_state(PaymentStates.enter_bot_amount)


@router.message(PaymentStates.enter_bot_amount)
async def enter_bot_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("Введите число. Попробуйте ещё раз:")
        return

    await state.update_data(amount=amount, price=amount)
    data = await state.get_data()
    await message.answer(
        f"Клиент: {data['client']}\nПериод: {data['period']}\nСумма: {amount} тг\nВыберите банк:",
        reply_markup=banks_kb("back:bot_amount")
    )
    await state.set_state(PaymentStates.choose_bank)


# ═══════════════════════════════════════════════════════════════════════════════
# УСЛУГИ: ПАКЕТЫ
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(PaymentStates.choose_package, F.data.startswith("pkg:"))
async def choose_package(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split(":")[1])
    await state.update_data(amount=amount, price=amount)
    data = await state.get_data()
    await callback.message.edit_text(
        f"Клиент: {data['client']}\nПакет: {amount} тг\nВыберите банк:",
        reply_markup=banks_kb("back:package")
    )
    await state.set_state(PaymentStates.choose_bank)


# ═══════════════════════════════════════════════════════════════════════════════
# ЛИЦЕНЗИИ: КОЛ-ВО → ПЕРИОД → ЦЕНА
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(PaymentStates.enter_qty)
async def enter_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число. Попробуйте ещё раз:")
        return
    await state.update_data(qty=qty)
    await message.answer(
        f"Количество: {qty}\nВыберите тариф:",
        reply_markup=periods_kb()
    )
    await state.set_state(PaymentStates.choose_period)


@router.callback_query(PaymentStates.choose_period, F.data.startswith("per:"))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]
    await state.update_data(period=period)
    data = await state.get_data()
    qty = data.get("qty", 1)
    months = PERIOD_MONTHS.get(period, 1)
    multiplier = months if months > 0 else 1
    new_price = PRICES_NEW.get(period, 0) * qty * multiplier
    old_price = PRICES_OLD.get(period, 0) * qty * multiplier
    await callback.message.edit_text(
        f"Тариф: {period}\nВыберите цену:",
        reply_markup=confirm_price_kb(new_price, old_price)
    )
    await state.set_state(PaymentStates.confirm_price)


@router.callback_query(PaymentStates.confirm_price, F.data.startswith("price:confirm:"))
async def confirm_price(callback: CallbackQuery, state: FSMContext):
    price = int(callback.data.split(":")[2])
    await state.update_data(price=price, amount=price)
    data = await state.get_data()
    await callback.message.edit_text(
        f"Сумма: {price} тг\nВыберите банк:",
        reply_markup=banks_kb()
    )
    await state.set_state(PaymentStates.choose_bank)


@router.callback_query(PaymentStates.confirm_price, F.data == "price:manual")
async def price_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите сумму вручную:")
    await state.set_state(PaymentStates.enter_price)


@router.message(PaymentStates.enter_price)
async def enter_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("Введите число. Попробуйте ещё раз:")
        return
    await state.update_data(price=price, amount=price)
    await message.answer(
        f"Сумма: {price} тг\nВыберите банк:",
        reply_markup=banks_kb()
    )
    await state.set_state(PaymentStates.choose_bank)


# ═══════════════════════════════════════════════════════════════════════════════
# БАНК → ДАТА → ЧЕК → ЗАПИСЬ
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(PaymentStates.choose_bank, F.data.startswith("bank:"))
async def choose_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split(":")[1]
    await state.update_data(bank=bank)
    await callback.message.edit_text(
        f"Банк: {bank}\nВыберите дату оплаты:",
        reply_markup=payment_date_kb()
    )
    await state.set_state(PaymentStates.choose_payment_date)


# ── Календарь: открыть ──
@router.callback_query(PaymentStates.choose_payment_date, F.data == 'pdate:cal')
async def open_calendar(callback: CallbackQuery, state: FSMContext):
    from datetime import datetime as dt
    tz = pytz.timezone('Asia/Almaty')
    now = dt.now(tz)
    await callback.message.edit_text(
        'Выберите дату:',
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
    date_str = callback.data.split(':', 2)[2]  # "06.04.2026"
    await state.update_data(payment_date=date_str)
    await callback.message.edit_text(
        "Отправьте фото/файл чека или нажмите 'Пропустить':",
        reply_markup=skip_receipt_kb()
    )
    await state.set_state(PaymentStates.upload_receipt)
    await callback.answer()


# ── Календарь: пустые кнопки ──
@router.callback_query(PaymentStates.choose_payment_date, F.data == 'pdate:noop')
async def noop_calendar(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(PaymentStates.choose_payment_date, F.data.startswith("pdate:"))
async def choose_payment_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[1]
    if date_str == "other":
        await callback.message.edit_text("Введите дату в формате ДД.ММ.ГГГГ:")
        await state.set_state(PaymentStates.enter_payment_date)
        return
    payment_date = date.fromisoformat(date_str)
    await state.update_data(payment_date=payment_date.strftime("%d.%m.%Y"))
    await callback.message.edit_text(
        "Отправьте фото/файл чека или нажмите 'Пропустить':",
        reply_markup=skip_receipt_kb()
    )
    await state.set_state(PaymentStates.upload_receipt)


@router.message(PaymentStates.enter_payment_date)
async def enter_payment_date(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(payment_date=dt.strftime("%d.%m.%Y"))
    except ValueError:
        await message.answer("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    await message.answer(
        "Отправьте фото/файл чека или нажмите 'Пропустить':",
        reply_markup=skip_receipt_kb()
    )
    await state.set_state(PaymentStates.upload_receipt)


# ═══════════════════════════════════════════════════════════════════════════════
# ЗАГРУЗКА ЧЕКА И ЗАПИСЬ
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(PaymentStates.upload_receipt, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    await state.update_data(receipt_file_id=photo.file_id)
    await save_payment(message, state, bot)


@router.message(PaymentStates.upload_receipt, F.document)
async def handle_receipt_document(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(receipt_file_id=message.document.file_id)
    await save_payment(message, state, bot)


@router.callback_query(PaymentStates.upload_receipt, F.data == "skip_receipt")
async def skip_receipt(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.update_data(receipt_file_id=None)
    await save_payment(callback.message, state, bot, callback=callback)


async def save_payment(message: Message, state: FSMContext, bot: Bot, callback=None):
    data = await state.get_data()
    cat_key = data.get("category_key", "")

    # Формируем строку для таблицы
    row_data = {
        "manager": data.get("manager", ""),
        "client": data.get("client", ""),
        "category": data.get("category", ""),
        "license_type": data.get("license_type", ""),
        "qty": data.get("qty", ""),
        "period": data.get("period", ""),
        "price": data.get("price", ""),
        "amount": data.get("amount", ""),
        "bank": data.get("bank", ""),
        "payment_date": data.get("payment_date", ""),
        "receipt_file_id": data.get("receipt_file_id", ""),
        "month": data.get("month"),
    }

    # Статус услуги для внедрений/интеграций
    if cat_key in STATUS_CATS:
        row_data["service_status"] = "Не выполнено"

    try:
        await add_payment(row_data)
        result_text = f"Оплата записана!\n{data.get('client')} - {data.get('amount')} тг"

        # Уведомление директору
        try:
            await bot.send_message(
                DIRECTOR_ID,
                f"Новая оплата:\nКлиент: {data.get('client')}\n"
                f"Сумма: {data.get('amount')} тг\nМенеджер: {data.get('manager')}"
            )
        except Exception as e:
            logger.error(f"Failed to notify director: {e}")

    except Exception as e:
        logger.error(f"Failed to save payment: {e}")
        result_text = f"Ошибка при записи: {e}"

    if callback:
        await callback.message.edit_text(result_text)
    else:
        await message.answer(result_text)

    # Если это новый клиент — спросить про услугу
    if cat_key == "new_client":
        if callback:
            await callback.message.answer(
                "Добавить услугу к этому клиенту?",
                reply_markup=add_service_kb()
            )
        else:
            await message.answer(
                "Добавить услугу к этому клиенту?",
                reply_markup=add_service_kb()
            )
        await state.set_state(PaymentStates.ask_add_service)
    else:
        await state.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# ДОБАВЛЕНИЕ УСЛУГИ К НОВОМУ КЛИЕНТУ
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(PaymentStates.ask_add_service, F.data == "add_service:yes")
async def add_service_yes(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите услугу:",
        reply_markup=service_categories_kb()
    )


@router.callback_query(PaymentStates.ask_add_service, F.data == "add_service:no")
async def add_service_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Готово!")
    await state.clear()


@router.callback_query(PaymentStates.ask_add_service, F.data == "add_service:done")
async def add_service_done(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Все услуги добавлены!")
    await state.clear()


@router.callback_query(PaymentStates.ask_add_service, F.data.startswith("svc:"))
async def choose_service_category(callback: CallbackQuery, state: FSMContext):
    svc_key = callback.data.split(":")[1]
    svc_label = next((label for key, label in CATEGORIES if key == svc_key), svc_key)

    # Сохраняем выбранную услугу
    data = await state.get_data()
    await state.update_data(category_key=svc_key, category=svc_label)

    # В зависимости от типа услуги
    if svc_key in MANUAL_AMOUNT_CATS:
        await callback.message.edit_text(f"Услуга: {svc_label}\nВведите сумму:")
        await state.set_state(PaymentStates.enter_manual_amount)
    elif svc_key in BOT_CATS:
        await callback.message.edit_text(
            f"Услуга: {svc_label}\nВыберите период:",
            reply_markup=bot_periods_kb()
        )
        await state.set_state(PaymentStates.choose_bot_period)
    else:
        await callback.message.edit_text(
            f"Услуга: {svc_label}\nВыберите пакет:",
            reply_markup=package_kb()
        )
        await state.set_state(PaymentStates.choose_package)


# ═══════════════════════════════════════════════════════════════════════════════
# КНОПКИ НАЗАД
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "back:month")
async def back_to_month(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите месяц:", reply_markup=months_kb())
    await state.set_state(PaymentStates.choose_month)


@router.callback_query(F.data == "back:category")
async def back_to_category(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Месяц: {data.get('month_name', '')}\nВыберите статью:",
        reply_markup=categories_kb()
    )
    await state.set_state(PaymentStates.choose_category)


@router.callback_query(F.data == "back:client")
async def back_to_client(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Статья: {data.get('category', '')}\nВведите название клиента:"
    )
    await state.set_state(PaymentStates.enter_client)


@router.callback_query(F.data == "back:qty")
async def back_to_qty(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Клиент: {data.get('client', '')}\nВведите количество лицензий:"
    )
    await state.set_state(PaymentStates.enter_qty)


@router.callback_query(F.data == "back:period")
async def back_to_period(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Количество: {data.get('qty', '')}\nВыберите тариф:",
        reply_markup=periods_kb()
    )
    await state.set_state(PaymentStates.choose_period)


@router.callback_query(F.data == "back:price")
async def back_to_price(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    qty = data.get("qty", 1)
    period = data.get("period", "Месячный")
    new_price = PRICES_NEW.get(period, 0) * qty
    old_price = PRICES_OLD.get(period, 0) * qty
    await callback.message.edit_text(
        f"Тариф: {period}\nВыберите цену:",
        reply_markup=confirm_price_kb(new_price, old_price)
    )
    await state.set_state(PaymentStates.confirm_price)


@router.callback_query(F.data == "back:package")
async def back_to_package(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Клиент: {data.get('client', '')}\nВыберите пакет:",
        reply_markup=package_kb()
    )
    await state.set_state(PaymentStates.choose_package)


@router.callback_query(F.data == "back:manual_amount")
async def back_to_manual_amount(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Клиент: {data.get('client', '')}\nВведите сумму:",
        reply_markup=manual_amount_kb()
    )
    await state.set_state(PaymentStates.enter_manual_amount)


@router.callback_query(F.data == "back:bot_amount")
async def back_to_bot_amount(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"Клиент: {data.get('client', '')}\nВыберите период:",
        reply_markup=bot_periods_kb()
    )
    await state.set_state(PaymentStates.choose_bot_period)


# ═══════════════════════════════════════════════════════════════════════════════
# ОТМЕНА
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cancel")
async def cancel_any(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.")

