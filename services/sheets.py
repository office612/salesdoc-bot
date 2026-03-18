import gspread
import logging
import json
import os
from datetime import datetime, date
from typing import Optional
import pytz
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, MONTH_SHEETS, TIMEZONE


logger = logging.getLogger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


DATA_START_ROW = 7


COL_DATE     = 0   # A
COL_COMPANY  = 1   # B
COL_ARTICLE  = 2   # C
COL_LICENSE  = 3   # D
COL_QTY      = 4   # E
COL_MANAGER  = 5   # F
COL_TARIFF   = 6   # G
COL_PRICE    = 7   # H
COL_PERIOD   = 8   # I
COL_AMOUNT   = 9   # J
COL_BANK     = 10  # K
COL_SEATED   = 11  # L
COL_FACT     = 12  # M


# Новые столбцы T-W (добавлены с апреля 2026)
COL_START_PERIOD = 19  # T
COL_ACT_DATE     = 20  # U
