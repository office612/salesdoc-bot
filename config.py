import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВИ_ТОКЕН")
SPREADSHEET_ID = "1WJJRqPvQ_i9jVhQgNc2Kuuynneu9jjTJwMGijCZHKho"
ACCOUNTANT_CHAT_ID = int(os.getenv("ACCOUNTANT_CHAT_ID", "-1001000000000"))
TIMEZONE = "Asia/Almaty"

MONTH_SHEETS = {
    1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
    7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек"
}

LEADER = "Мирзахаит"
EMPLOYEES = {
    "managers": ["Айдос", "Айдос Хапез", "Юлия", "Акбар", "Самат"],
    "accountants": ["Гульшан", "Аурика"],
}

CATEGORIES = [
    ("salesdoc", "SalesDoc"),
    ("svetofor", "Светофор"),
    ("other", "Другое"),
]

LICENSE_TYPES = ["1 место", "2 места", "3 места", "5 мест", "10 мест", "20 мест", "50 мест", "100+ мест"]

PERIODS = ["1 мес", "3 мес", "6 мес", "12 мес"]

BANKS = ["Каспи Банк", "Халык Банк", "Наличные"]
