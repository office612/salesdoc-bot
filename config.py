import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "VSTAVI_TOKEN")

# Таблица Доходы KZ 2026
SPREADSHEET_ID = "1WJJRqPvQ_i9jVhQgNc2Kuuynneu9jjTJwMGijCZKHbo"

# ID для уведомлений
DIRECTOR_ID = 5472344802
ACCOUNTANT_IDS = [
        int(x.strip()) for x in os.getenv("ACCOUNTANT_IDS", "").split(",") if x.strip()
]

TIMEZONE = "Asia/Almaty"

MONTH_SHEETS = {
        1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр",
        5: "Май", 6: "Июн", 7: "Июл", 8: "Авг",
        9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек",
}

LEADER = "Мирзахит"
EMPLOYEES = {
        "managers": ["Мирзахит", "Айдос Хапез", "Юлия", "Акбар", "Самат"],
        "accountants": ["Гульшан", "Аурика"],
}

# Статья (колонка C) — как в раскрывающемся списке таблицы
CATEGORIES = [
        ("abon_plata",   "абон. плата"),
        ("dop_lic",      "доп. лицензии"),
        ("oplata_dolga", "Оплата долга"),
        ("nakladnaya",   "наклодная"),
        ("balans",       "баланс"),
        ("usluga",       "Услуга"),
]

# Лицензии аген/экс/мерч... (колонка D)
LICENSE_TYPES = ["Лицензии", "Баланс", "Услуга"]

# Тариф (колонка G)
PERIODS = ["Месячный", "3 месячный", "6 месячный", "12 месяцев", "Баланс", "Услуга"]

# Банк (колонка K)
BANKS = ["каспи", "халык", "Forte", "BCC", "Jusan"]
