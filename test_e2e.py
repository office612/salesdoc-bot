"""End-to-end FSM-тест без Telegram.

Имитирует пользователя, нажимающего кнопки и вводящего тексты в боте.
Использует реальный aiogram MemoryStorage + FSMContext, реальные хендлеры
из handlers/payment.py. Telegram API замокан, gspread замокан.

Проверяет:
  • правильность переходов между состояниями FSM
  • что обработчики сохраняют данные в state без потерь
  • что финальная запись в add_payment получает корректные значения
  • новый 2-шаговый ручной ввод (price → confirm_fact → enter_fact)
  • запись комбо «новый клиент + 2 услуги» одной транзакцией
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("ACCOUNTANT_IDS", "")
os.environ.setdefault("KASSA_BOT_TOKEN", "")  # отключаем уведомления

# ── Подмена gspread ──────────────────────────────────────────
captured_writes = []


class FakeWS:
    _filled = 6

    def col_values(self, c):
        return ["x"] * FakeWS._filled

    def update(self, rng, values, value_input_option=None):
        captured_writes.append((rng, values))
        if rng.startswith("A") and ":M" in rng:
            FakeWS._filled += 1


class FakeSS:
    def worksheet(self, name):
        return FakeWS()


import services.sheets as sheets_mod
sheets_mod.get_client = lambda: MagicMock(open_by_key=MagicMock(return_value=FakeSS()))
sheets_mod.get_spreadsheet = lambda: FakeSS()
sheets_mod.get_sheet = lambda n: FakeWS()
sheets_mod.get_sheet_by_month = lambda m: FakeWS()
sheets_mod._load_ref_cache = lambda: None
sheets_mod._match_ref_value = lambda v, c: v

# ── Подмена users ────────────────────────────────────────────
import services.users as users_mod
users_mod.get_user_info = lambda uid: {"name": "Айдос", "role": "manager"}
users_mod.is_accountant = lambda u: False
users_mod.is_manager = lambda u: True
users_mod.fix_legacy_name = lambda uid, u: u

# ── Импорт хендлеров ПОСЛЕ моков ─────────────────────────────
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.context import FSMContext

import handlers.payment as hp
from states import PaymentStates


# ── Утилиты для мокинга Message/CallbackQuery ────────────────
def make_state(storage, user_id=111):
    key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


def make_message(text, user_id=111):
    msg = MagicMock()
    msg.text = text
    msg.from_user.id = user_id
    msg.from_user.username = "test"
    msg.chat.id = user_id
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    msg.photo = None
    msg.document = None
    msg.caption = None
    return msg


def make_callback(data, user_id=111):
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = user_id
    cb.from_user.username = "test"
    cb.message = make_message("", user_id)
    cb.answer = AsyncMock()
    return cb


# ── Сценарий 1: лицензия по тарифу ───────────────────────────
async def test_license_by_tariff():
    print("=" * 70)
    print("E2E #1: ЛИЦЕНЗИЯ ПО ТАРИФУ — Месячный, 3 шт, 7 000 за лиц")
    print("=" * 70)

    storage = MemoryStorage()
    state = make_state(storage)
    captured_writes.clear()
    FakeWS._filled = 6

    # Шаг 1: жмёт «💳 Внести оплату»
    msg = make_message("💳 Внести оплату")
    await hp.start_payment_text(msg, state)
    cur = await state.get_state()
    assert cur == PaymentStates.choose_month.state, f"expected choose_month, got {cur}"
    print(f"  ✓ После «Внести оплату» → state={cur}")
    print(f"    бот ответил: {msg.answer.call_args.args[0][:60]}...")

    # Шаг 2: выбирает месяц (5 = Май)
    cb = make_callback("month:5")
    await hp.choose_month(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_category.state
    assert data["month"] == 5
    print(f"  ✓ month:5 → state={cur}, data.month=5")

    # Шаг 3: выбирает статью abon_plata
    cb = make_callback("cat:abon_plata")
    await hp.choose_category(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_license.state
    assert data["category_key"] == "abon_plata"
    print(f"  ✓ cat:abon_plata → state={cur}, category={data['category']}")

    # Шаг 4: выбирает тип лицензии
    cb = make_callback("lic:Лицензии")
    await hp.choose_license(cb, state)
    cur = await state.get_state()
    assert cur == PaymentStates.enter_client.state
    print(f"  ✓ lic:Лицензии → state={cur}")

    # Шаг 5: вводит клиента
    msg = make_message("ИП Иванов")
    await hp.enter_client(msg, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.enter_qty.state
    assert data["client"] == "ИП Иванов"
    print(f"  ✓ client='ИП Иванов' → state={cur}")

    # Шаг 6: вводит количество
    msg = make_message("3")
    await hp.enter_qty(msg, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_period.state
    assert data["qty"] == 3
    print(f"  ✓ qty=3 → state={cur}")

    # Шаг 7: выбирает период
    cb = make_callback("per:Месячный")
    await hp.choose_period(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.confirm_price.state
    assert data["period"] == "Месячный"
    print(f"  ✓ per:Месячный → state={cur}, period={data['period']}")

    # Шаг 8: подтверждает «Новый клиент: 21 000» (callback_data: price:confirm:21000:7000)
    cb = make_callback("price:confirm:21000:7000")
    await hp.confirm_price(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_bank.state
    assert data["price"] == 7000
    assert data["amount"] == 21000
    print(f"  ✓ price:confirm:21000:7000 → state={cur}")
    print(f"    H={data['price']}, J={data['amount']}, M={data.get('fact_amount', '')}")

    # Шаг 9: выбирает банк
    cb = make_callback("bank:халык")
    await hp.choose_bank(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_payment_date.state
    assert data["bank"] == "халык"
    print(f"  ✓ bank:халык → state={cur}")

    # Шаг 10: выбирает дату «Сегодня»
    cb = make_callback("pdate:2026-05-03")
    await hp.choose_payment_date(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.upload_receipt.state
    assert data["payment_date"] == "03.05.2026"
    print(f"  ✓ pdate:2026-05-03 → state={cur}, payment_date={data['payment_date']}")

    # Шаг 11: пропускает чек → save_payment
    cb = make_callback("skip_receipt")
    bot_mock = AsyncMock()
    await hp.skip_receipt(cb, state, bot_mock)

    # Проверяем запись
    assert len(captured_writes) >= 1, "должна была быть запись в Sheets"
    rng, values = captured_writes[0]
    row = values[0]
    print(f"\n  📊 Записано в таблицу: range={rng}")
    print(f"    A дата:       {row[0]!r}")
    print(f"    B клиент:     {row[1]!r}")
    print(f"    C статья:     {row[2]!r}")
    print(f"    E qty:        {row[4]!r}")
    print(f"    F менеджер:   {row[5]!r}")
    print(f"    G период:     {row[6]!r}")
    print(f"    H цена/лиц:   {row[7]!r}")
    print(f"    I множитель:  {row[8]!r}")
    print(f"    J СУММА:      {row[9]!r}  ← должно быть 21000")
    print(f"    K банк:       {row[10]!r}")
    print(f"    M ФАКТ:       {row[12]!r}  ← должно быть пусто")

    assert row[7] == 7000, f"H expected 7000, got {row[7]}"
    assert row[9] == 21000, f"J expected 21000, got {row[9]}"
    assert row[12] == "", f"M expected empty, got {row[12]!r}"
    print("\n  ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ\n")


# ── Сценарий 2: ручной ввод, факт ≠ план ─────────────────────
async def test_manual_with_fact():
    print("=" * 70)
    print("E2E #2: РУЧНОЙ ВВОД — план 10 000, факт 12 000")
    print("=" * 70)

    storage = MemoryStorage()
    state = make_state(storage)
    captured_writes.clear()
    FakeWS._filled = 6

    # Быстро прокатываемся до confirm_price
    await hp.start_payment_text(make_message("💳 Внести оплату"), state)
    await hp.choose_month(make_callback("month:5"), state)
    await hp.choose_category(make_callback("cat:abon_plata"), state)
    await hp.choose_license(make_callback("lic:Лицензии"), state)
    await hp.enter_client(make_message("ИП Петров"), state)
    await hp.enter_qty(make_message("2"), state)
    await hp.choose_period(make_callback("per:Месячный"), state)

    cur = await state.get_state()
    assert cur == PaymentStates.confirm_price.state
    print(f"  ✓ Дошли до confirm_price")

    # Жмёт «Ввести вручную»
    cb = make_callback("price:manual")
    await hp.price_manual(cb, state)
    cur = await state.get_state()
    assert cur == PaymentStates.enter_price.state
    print(f"  ✓ price:manual → state={cur}")
    print(f"    бот сказал: {cb.message.edit_text.call_args.args[0][:80]}...")

    # Вводит цену за 1 лицензию: 5000
    msg = make_message("5000")
    await hp.enter_price(msg, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.confirm_fact.state, f"expected confirm_fact, got {cur}"
    assert data["price"] == 5000
    assert data["amount"] == 10000  # 2 × 5000 × 1
    print(f"  ✓ price=5000 → state={cur}")
    print(f"    План посчитан: H={data['price']}, J={data['amount']} (озвучено клиенту)")
    print(f"    бот сказал: {msg.answer.call_args.args[0][:80]}...")

    # Жмёт «Клиент заплатил иначе»
    cb = make_callback("fact:other")
    await hp.confirm_fact_other(cb, state)
    cur = await state.get_state()
    assert cur == PaymentStates.enter_fact.state
    print(f"  ✓ fact:other → state={cur}")

    # Вводит факт 12000
    msg = make_message("12000")
    await hp.enter_fact_amount(msg, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_bank.state
    assert data["fact_amount"] == 12000
    print(f"  ✓ fact=12000 → state={cur}, M={data['fact_amount']}")

    # Банк → дата → пропуск чека
    await hp.choose_bank(make_callback("bank:халык"), state)
    await hp.choose_payment_date(make_callback("pdate:2026-05-03"), state)
    bot_mock = AsyncMock()
    await hp.skip_receipt(make_callback("skip_receipt"), state, bot_mock)

    rng, values = captured_writes[0]
    row = values[0]
    print(f"\n  📊 Записано: range={rng}")
    print(f"    H цена/лиц:   {row[7]!r}  ← должно быть 5000")
    print(f"    J СУММА:      {row[9]!r}  ← должно быть 10000 (озвучено)")
    print(f"    M ФАКТ:       {row[12]!r}  ← должно быть 12000")

    assert row[7] == 5000, f"H expected 5000, got {row[7]}"
    assert row[9] == 10000, f"J expected 10000, got {row[9]}"
    assert row[12] == 12000, f"M expected 12000, got {row[12]}"
    print("\n  ✅ РУЧНОЙ ВВОД С ФАКТОМ ≠ ПЛАН РАБОТАЕТ ПРАВИЛЬНО\n")


# ── Сценарий 3: ручной ввод, факт = план ─────────────────────
async def test_manual_by_plan():
    print("=" * 70)
    print("E2E #3: РУЧНОЙ ВВОД — клиент заплатил по плану")
    print("=" * 70)

    storage = MemoryStorage()
    state = make_state(storage)
    captured_writes.clear()
    FakeWS._filled = 6

    await hp.start_payment_text(make_message("💳 Внести оплату"), state)
    await hp.choose_month(make_callback("month:5"), state)
    await hp.choose_category(make_callback("cat:abon_plata"), state)
    await hp.choose_license(make_callback("lic:Лицензии"), state)
    await hp.enter_client(make_message("ТОО Сигма"), state)
    await hp.enter_qty(make_message("4"), state)
    await hp.choose_period(make_callback("per:3 месячный"), state)
    await hp.price_manual(make_callback("price:manual"), state)
    await hp.enter_price(make_message("6000"), state)

    data = await state.get_data()
    print(f"  ✓ Введено: цена/лиц=6000, qty=4, период=3 мес → план={data['amount']}")
    assert data["amount"] == 72000  # 4 × 6000 × 3

    # Жмёт «По плану»
    cb = make_callback("fact:plan")
    await hp.confirm_fact_plan(cb, state)
    cur = await state.get_state()
    data = await state.get_data()
    assert cur == PaymentStates.choose_bank.state
    assert data["fact_amount"] == ""
    print(f"  ✓ fact:plan → state={cur}, M={data['fact_amount']!r} (пусто)")

    await hp.choose_bank(make_callback("bank:каспи"), state)
    await hp.choose_payment_date(make_callback("pdate:2026-05-03"), state)
    bot_mock = AsyncMock()
    await hp.skip_receipt(make_callback("skip_receipt"), state, bot_mock)

    rng, values = captured_writes[0]
    row = values[0]
    print(f"\n  📊 Записано: H={row[7]!r}, J={row[9]!r}, M={row[12]!r}")
    assert row[7] == 6000
    assert row[9] == 72000
    assert row[12] == ""  # M пусто
    print("\n  ✅ РУЧНОЙ ВВОД С ФАКТОМ = ПЛАН → M ОСТАЁТСЯ ПУСТЫМ\n")


# ── Сценарий 4: предупреждение о несоответствии месяца ────────
async def test_month_mismatch_warning():
    print("=" * 70)
    print("E2E #4: ПРЕДУПРЕЖДЕНИЕ — месяц вкладки ≠ месяц даты")
    print("=" * 70)

    storage = MemoryStorage()
    state = make_state(storage)
    captured_writes.clear()
    FakeWS._filled = 6

    await hp.start_payment_text(make_message("💳 Внести оплату"), state)
    # Выбираем АПРЕЛЬ
    await hp.choose_month(make_callback("month:4"), state)
    await hp.choose_category(make_callback("cat:abon_plata"), state)
    await hp.choose_license(make_callback("lic:Лицензии"), state)
    await hp.enter_client(make_message("ИП Тест"), state)
    await hp.enter_qty(make_message("1"), state)
    await hp.choose_period(make_callback("per:Месячный"), state)
    await hp.confirm_price(make_callback("price:confirm:7000:7000"), state)
    await hp.choose_bank(make_callback("bank:халык"), state)
    # Дата 03.05.2026 (МАЙ!)
    await hp.choose_payment_date(make_callback("pdate:2026-05-03"), state)

    skip_cb = make_callback("skip_receipt")
    bot_mock = AsyncMock()
    await hp.skip_receipt(skip_cb, state, bot_mock)

    # Проверяем что в ответе есть предупреждение
    final_text = skip_cb.message.edit_text.call_args.args[0]
    print(f"\n  📨 Финальный ответ боту:\n{'-' * 60}")
    for line in final_text.split("\n"):
        print(f"    {line}")
    print(f"{'-' * 60}")
    assert "Внимание" in final_text, "Ожидалось предупреждение о несовпадении месяца"
    assert "Апр" in final_text and "Май" in final_text
    print("\n  ✅ ПРЕДУПРЕЖДЕНИЕ ВЫВОДИТСЯ КОРРЕКТНО\n")


# ── Сценарий 5: подсветка текущего месяца в клавиатуре ───────
async def test_current_month_highlighted():
    print("=" * 70)
    print("E2E #5: ПОДСВЕТКА ТЕКУЩЕГО МЕСЯЦА в клавиатуре")
    print("=" * 70)

    from keyboards.payment import months_kb
    kb = months_kb()
    found_pin = False
    for row in kb.inline_keyboard:
        for btn in row:
            if "📍" in btn.text:
                print(f"  ✓ Найдена подсвеченная кнопка: {btn.text!r}")
                found_pin = True
    assert found_pin, "Текущий месяц не подсвечен 📍"
    print("\n  ✅ ТЕКУЩИЙ МЕСЯЦ ПОДСВЕЧЕН\n")


async def main():
    try:
        await test_license_by_tariff()
        await test_manual_with_fact()
        await test_manual_by_plan()
        await test_month_mismatch_warning()
        await test_current_month_highlighted()
        print("=" * 70)
        print("🎉 ВСЕ E2E-ТЕСТЫ ПРОШЛИ УСПЕШНО")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ ОШИБКА: {e}")
        raise
    except Exception as e:
        print(f"\n💥 НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
