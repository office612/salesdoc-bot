import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВИ_СВОЙ_TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = "1WJJRqPvQ_i9jVhQgNc2Kuuynneu9jjTJwMGijCZHKho"
ACCOUNTANT_CHAT_ID = int(os.getenv("ACCOUNTANT_CHAT_ID", "-1001000000000"))

MONTH_SHEETS = {
    1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
    7: "Љrл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек�
}
