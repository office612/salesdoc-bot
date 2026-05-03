"""Имитация реального flow без подключения к Google Sheets.

Подменяет gspread на mock и прогоняет add_payment с разными data-словарями,
которые формирует FSM в handlers/payment.py для каждого сценария.

Не запускает бота, не пишет в таблицу — только показывает, что бы записалось.
"""
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

# Заглушки env, чтобы config импортнулся
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("ACCOUNTANT_IDS", "")

# Перехватываем gspread, чтобы не открывать реальную таблицу
captured_writes = []  # сюда складываем все ws.update()


class FakeWS:
    """Притворяемся, что в листе уже есть _filled_rows строк.

    После каждого update() инкрементируем счётчик, чтобы следующая запись
    шла на следующую строку — как при последовательной записи 3 строк
    (лицензия + 2 услуги одной транзакцией).
    """
    _filled_rows = 6

    def col_values(self, col):
        return ["x"] * FakeWS._filled_rows

    def update(self, rng, values, value_input_option=None):
        captured_writes.append((rng, values))
        # Если это запись A:M — инкрементируем счётчик строк
        if rng.startswith("A") and ":M" in rng:
            FakeWS._filled_rows += 1


class FakeSS:
    def worksheet(self, name):
        return FakeWS()


def fake_get_client():
    cli = MagicMock()
    cli.open_by_key.return_value = FakeSS()
    return cli


# Подменяем до импорта sheets
import services.sheets as sheets_mod
sheets_mod.get_client = fake_get_client
sheets_mod.get_spreadsheet = lambda: FakeSS()
sheets_mod.get_sheet = lambda name: FakeWS()
sheets_mod.get_sheet_by_month = lambda m: FakeWS()
sheets_mod._load_ref_cache = lambda: None        # не лезем за справочником
sheets_mod._match_ref_value = lambda v, c: v     # справочник = identity


from services.sheets import add_payment


# ── Сценарии (data-словари как их формирует FSM) ─────────────
SCENARIOS = [
    {
        "title": "1) Лицензия по формуле, Новый клиент",
        "data": {
            "month": 5,
            "manager": "Айдос",
            "client": "ИП Иванов",
            "category": "абон. плата",
            "category_key": "abon_plata",
            "license_type": "Лицензии",
            "qty": 3,
            "period": "Месячный",
            "price": 7000,        # цена за 1 лицензию (по тарифу)
            "amount": 21000,      # qty*price*1
            "fact_amount": "",
            "bank": "халык",
            "payment_date": "03.05.2026",
        },
    },
    {
        "title": "2) Лицензия по формуле, 3 месяца",
        "data": {
            "month": 5,
            "manager": "Айдос",
            "client": "ТОО Альфа",
            "category": "абон. плата",
            "category_key": "abon_plata",
            "license_type": "Лицензии",
            "qty": 5,
            "period": "3 месячный",
            "price": 7000,
            "amount": 105000,     # 5*7000*3
            "fact_amount": "",
            "bank": "каспи",
            "payment_date": "03.05.2026",
        },
    },
    {
        "title": "3a) ⭐ Ручной ввод, факт = плану (5 000/лиц × 2 × 1 = 10 000)",
        "data": {
            "month": 5,
            "manager": "Юлия",
            "client": "ИП Петров",
            "category": "абон. плата",
            "category_key": "abon_plata",
            "license_type": "Лицензии",
            "qty": 2,
            "period": "Месячный",
            "price": 5000,        # цена за 1 лиц (ввёл вручную)
            "amount": 10000,      # план = qty*price*1 (озвучено клиенту)
            "fact_amount": "",    # факт = плану → M пусто
            "bank": "халык",
            "payment_date": "03.05.2026",
        },
    },
    {
        "title": "3b) ⭐ Ручной ввод, факт ≠ плана (план 10 000, факт 12 000)",
        "data": {
            "month": 5,
            "manager": "Юлия",
            "client": "ИП Петров",
            "category": "абон. плата",
            "category_key": "abon_plata",
            "license_type": "Лицензии",
            "qty": 2,
            "period": "Месячный",
            "price": 5000,        # H = 5000
            "amount": 10000,      # J = 10000 (озвучено)
            "fact_amount": 12000, # M = 12000 (реально пришло)
            "bank": "халык",
            "payment_date": "03.05.2026",
        },
    },
    {
        "title": "4) Услуга — Накладная (ручная сумма)",
        "data": {
            "month": 5,
            "manager": "Самат",
            "client": "ТОО Бета",
            "category": "наклодная",
            "category_key": "nakladnaya",
            "license_type": "Услуга",
            "qty": "",
            "period": "Услуга",
            "price": 50000,
            "amount": 50000,
            "fact_amount": "",
            "bank": "Наличка",
            "payment_date": "03.05.2026",
        },
    },
    {
        "title": "5) Бот — Бот заказ, период 6 месяцев",
        "data": {
            "month": 5,
            "manager": "Акбар",
            "client": "ИП Сидоров",
            "category": "Бот заказ",
            "category_key": "bot_zakaz",
            "license_type": "Услуга",
            "qty": "",
            "period": "6 месяцев",
            "price": 18000,
            "amount": 18000,
            "fact_amount": "",
            "bank": "каспи",
            "payment_date": "03.05.2026",
        },
    },
    {
        "title": "6) Услуга-пакет — Нов. внедрение, Пакет 199 000",
        "data": {
            "month": 5,
            "manager": "Мирзахит",
            "client": "ТОО Гамма",
            "category": "Нов внедрение",
            "category_key": "nov_vnedrenie",
            "license_type": "Услуга",
            "qty": "",
            "period": "Услуга",
            "price": 199000,
            "amount": 199000,
            "fact_amount": "",
            "bank": "халык",
            "payment_date": "03.05.2026",
        },
    },
]

# ── Комбо: новый клиент + 2 услуги одной записью ─────────────
# Имитируем то, что собирает save_payment в payments_to_save:
#   payments_to_save = [main_payment] + services_list
# Каждый словарь идёт в add_payment отдельной строкой, но с общими
# manager / client / bank / payment_date / month.
COMBO_SCENARIO = {
    "title": "7) КОМБО: Новый клиент (5 лиц × 7 000) + 2 услуги одной записью",
    "shared": {
        "month": 5,
        "manager": "Айдос",
        "client": "ТОО Дельта",
        "bank": "халык",
        "payment_date": "03.05.2026",
    },
    "items": [
        {  # main_payment — лицензии нового клиента
            "category": "новый клиент",
            "category_key": "new_client",
            "license_type": "Лицензии",
            "qty": 5,
            "period": "Месячный",
            "price": 7000,
            "amount": 35000,        # 5 × 7000 × 1
            "fact_amount": "",
        },
        {  # services_list[0] — Нов. внедрение, Пакет 199 000
            "category": "Нов внедрение",
            "category_key": "nov_vnedrenie",
            "license_type": "Услуга",
            "qty": "",
            "period": "Услуга",
            "price": 199000,
            "amount": 199000,
            "fact_amount": "",
        },
        {  # services_list[1] — Нов. интеграция, Пакет 99 000
            "category": "Нов интеграция",
            "category_key": "nov_integr",
            "license_type": "Услуга",
            "qty": "",
            "period": "Услуга",
            "price": 99000,
            "amount": 99000,
            "fact_amount": "",
        },
    ],
}


COL_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
COL_MEANING = [
    "Дата", "Клиент", "Статья", "Лицензия", "Кол-во",
    "Менеджер", "Тариф", "Цена/лиц", "Период", "Сумма",
    "Банк", "Посажено", "ФАКТ",
]


def show_row(rng, values):
    row = values[0]
    print(f"   range: {rng}")
    width = max(len(m) for m in COL_MEANING)
    for i, val in enumerate(row):
        letter = COL_LETTERS[i] if i < len(COL_LETTERS) else "?"
        meaning = COL_MEANING[i] if i < len(COL_MEANING) else ""
        marker = ""
        if letter == "J":
            marker = "  ← СУММА (по формуле)"
        if letter == "M":
            marker = "  ← ФАКТ (ручной ввод)"
        if letter == "H":
            marker = "  ← цена за 1 лицензию"
        print(f"     {letter} {meaning:<{width}}: {val!r:<15}{marker}")


def show_writes(writes):
    """Показывает все captured writes (A:M и T:W) одной записи."""
    for i, (rng, values) in enumerate(writes):
        if rng.startswith("A") and ":M" in rng:
            print("\n  Запись в основные столбцы A:M ↓")
            show_row(rng, values)
        else:
            print(f"\n  Запись в доп. столбцы {rng}:")
            row = values[0]
            for j, val in enumerate(row):
                letter = ["T", "U", "V", "W"][j]
                label = ["Нач. период", "Дата активации", "Цена акта", "Статус услуги"][j]
                print(f"     {letter} {label:<18}: {val!r}")


async def main():
    # Сбрасываем счётчик строк перед прогоном одиночных сценариев
    FakeWS._filled_rows = 6

    for sc in SCENARIOS:
        print("=" * 70)
        print(sc["title"])
        print("=" * 70)
        captured_writes.clear()
        # Каждый одиночный сценарий — независимая запись на 7-ю строку
        FakeWS._filled_rows = 6
        try:
            row_num = await add_payment(sc["data"])
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            continue
        show_writes(captured_writes)
        print()

    # ── Комбо: новый клиент + 2 услуги одной записью ─────────
    print("=" * 70)
    print(COMBO_SCENARIO["title"])
    print("=" * 70)
    print("Имитируем save_payment: одна транзакция → 3 строки подряд")
    print("(лицензия + 2 услуги; manager/client/bank/date/month — общие)\n")

    FakeWS._filled_rows = 6  # начинаем со строки 7
    total_amount = 0
    row_nums = []

    for idx, item in enumerate(COMBO_SCENARIO["items"]):
        # Собираем row_data так же, как save_payment
        row_data = dict(COMBO_SCENARIO["shared"])
        row_data.update(item)

        captured_writes.clear()
        try:
            row_num = await add_payment(row_data)
        except Exception as e:
            print(f"   ❌ ОШИБКА на строке {idx}: {e}")
            continue

        row_nums.append(row_num)
        try:
            total_amount += int(item.get("amount", 0) or 0)
        except (ValueError, TypeError):
            pass

        marker = "🪪 ЛИЦЕНЗИЯ" if idx == 0 else f"🛠 УСЛУГА #{idx}"
        print(f"\n──── {marker} (строка {row_num}) ────")
        show_writes(captured_writes)

    print()
    print("=" * 70)
    print(f"ИТОГ КОМБО:")
    print(f"  Записаны строки:  {row_nums}")
    print(f"  Общая сумма (J):  {total_amount:,} тг".replace(",", " "))
    print(f"  Менеджер: {COMBO_SCENARIO['shared']['manager']}")
    print(f"  Клиент:   {COMBO_SCENARIO['shared']['client']}")
    print(f"  Банк:     {COMBO_SCENARIO['shared']['bank']}")
    print(f"  Дата:     {COMBO_SCENARIO['shared']['payment_date']}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
