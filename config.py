import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "VSTAVI_TOKEN")
SPREADSHEET_ID = "1eplXgMIfr-xyM3wWMCrPPomeTh6LhCm7zmHc1HoSm8E"
ACCOUNTANT_CHAT_ID = int(os.getenv("ACCOUNTANT_CHAT_ID", "-1001000000000"))
TIMEZONE = "Asia/Almaty"

MONTH_SHEETS = {
    1: "Yan", 2: "Fev", 3: "Mar", 4: "Apr", 5: "May", 6: "Iyun",
    7: "Iyul", 8: "Avg", 9: "Sen", 10: "Okt", 11: "Noy", 12: "Dek"
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
