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

# Маппинг Telegram username → имя из раскрывающегося списка таблицы
USERNAME_TO_NAME = {
        "sdsolutionkz": "Айдос",
        "sdkzhst":      "Акбар",
        "samat9827":    "Самат",
}

# Статья (колонка C) — точно по справочнику таблицы Доходы KZ 2026
CATEGORIES = [
        ("abon_plata",      "абон. плата"),
        ("dop_lic",         "доп. лицензии"),
        ("new_client",      "новый клиент"),
        ("nov_vnedrenie",   "Нов внедрение"),
        ("nov_integr",      "Нов интеграция"),
        ("sta_vnedrenie",   "Ста внедрение"),
        ("sta_integr",      "Ста интеграция"),
        ("nakladnaya",      "наклодная"),
        ("oplata_dolga",    "Оплата долга"),
        ("balans",          "баланс"),
        ("dorabotka",       "доработка"),
        ("telegram_boty",   "телеграм боты"),
        ("integr_plus",     "интеграция +"),
        ("dop_obuchenie",   "доп обучение"),
        ("dvagis",          "2гис"),
        ("shtrafy",         "Штрафы"),
        ("bonus",           "Бонус"),
        ("prochie",         "Прочие доходы"),
        ("vozvrat",         "Возврат"),
        ("ne_naznacheno",   "Не назначено"),
]

# Лицензии аген/экс/мерч... (колонка D)
LICENSE_TYPES = ["Лицензии", "Баланс", "Услуга"]

# Тариф (колонка G)
PERIODS = [
    "10 дней",
    "20 дней",
    "Месячный",
    "3 месячный",
    "6 месячный",
    "12 месяцев",
    "Баланс",
    "Услуга",
]

# Банк (колонка K)
BANKS = ["халык", "каспи", "Наличка"]

# ── Цены за лицензию по тарифу ──────────────────────────────
# Новые клиенты (с 01.03.2026)
PRICES_NEW = {
    "10 дней":    3000,
    "20 дней":    4000,
    "Месячный":   7000,
    "3 месячный": 7000,
    "6 месячный": 5600,
    "12 месяцев": 5600,
}

# Старые клиенты (до 01.03.2026)
PRICES_OLD = {
    "10 дней":    3000,
    "20 дней":    4000,
    "Месячный":   7000,
    "3 месячный": 5000,
    "6 месячный": 4500,
    "12 месяцев": 4000,
}

# Маппинг периода → кол-во месяцев
PERIOD_MONTHS = {
    "10 дней":    0,
    "20 дней":    0,
    "Месячный":   1,
    "3 месячный": 3,
    "6 месячный": 6,
    "12 месяцев": 12,
}

# Дата разграничения новых/старых клиентов
NEW_CLIENT_DATE = "2026-03-01"

# Категории-услуги: без лицензии/кол-ва/тарифа → сразу клиент → пакет/сумма
SERVICE_CATS = {
    'nov_vnedrenie', 'nov_integr', 'sta_vnedrenie', 'sta_integr',
    'nakladnaya', 'oplata_dolga', 'dorabotka', 'telegram_boty',
    'integr_plus', 'dop_obuchenie', 'dvagis', 'shtrafy', 'bonus',
    'prochie', 'vozvrat', 'ne_naznacheno',
}

# Категории для которых ставим "Не выполнено" в столбце W (Статус услуги)
STATUS_CATS = {'nov_vnedrenie', 'nov_integr', 'sta_vnedrenie', 'sta_integr'}
