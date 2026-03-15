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

LEADER = "Mirzahait"
EMPLOYEES = {
        "managers": ["Aidos", "Aidos Hapez", "Yulia", "Akbar", "Samat"],
        "accountants": ["Gulshan", "Aurika"],
}

CATEGORIES = [
        ("salesdoc", "SalesDoc"),
        ("other", "Drugoe"),
]

LICENSE_TYPES = ["Bazoviy", "Standart", "Premium"]
PERIODS = ["1 mes", "3 mes", "6 mes", "12 mes"]
BANKS = ["Kaspi", "Halyk", "BCC", "Jusan", "Forte"]
