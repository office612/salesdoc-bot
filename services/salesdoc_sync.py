"""Синхронизация оплат с SalesDoc dashboard.

После того как бот записал строку оплаты в Доходы 2026, мы дополнительно
шлём её в SalesDoc API. Там:
  - 'Нов внедрение' / 'Нов интеграция'  → создаётся карточка в Маршруте
  - 'абон. плата'                        → продлевается next_billing_at клиента

Если SalesDoc недоступен — логируем и идём дальше. Запись в Sheets важнее,
ради синхронизации не падаем (бухгалтерия не должна страдать).

Env:
  SALESDOC_URL        — базовый URL дашборда (по умолчанию prod)
  SALESDOC_APP_TOKEN  — shared secret APP_TOKEN из .env Vercel (тот же что у фронта)
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SALESDOC_URL = os.getenv("SALESDOC_URL", "https://salesdoc-app.vercel.app")
APP_TOKEN = os.getenv("SALESDOC_APP_TOKEN", "")


def _period_to_months(period: str) -> int:
    """Маппинг строкового тарифа в число месяцев. Совпадает с PERIOD_MONTHS в config.py."""
    p = str(period or "").strip()
    return {
        "Месячный": 1,
        "3 месячный": 3,
        "6 месячный": 6,
        "12 месяцев": 12,
    }.get(p, 1)


def sync_payment_to_salesdoc(data: dict, row_num: int, country: str = "KZ") -> Optional[dict]:
    """Шлёт оплату в SalesDoc.

    data — словарь как в add_payment (категория, клиент, тариф, сумма ...).
    row_num — номер строки в Google Sheets (нужен для idempotency).

    Возвращает ответ SalesDoc или None если не настроен/упал.
    """
    if not APP_TOKEN:
        logger.info("SalesDoc sync skipped: SALESDOC_APP_TOKEN not set")
        return None

    category_label = data.get("category_label") or data.get("category") or ""
    payload = {
        "source": "payment_bot",
        "company": data.get("client") or data.get("company") or "",
        "category": category_label,
        "tariff": data.get("period") or data.get("tariff") or "",
        "period_months": _period_to_months(data.get("period") or data.get("tariff")),
        "amount": data.get("amount") or 0,
        "manager": data.get("manager") or "",
        "sheet_row": row_num,
        "sheet_month": int(data.get("month") or 0),
        "country": country,
    }

    try:
        r = requests.post(
            f"{SALESDOC_URL}/api/cards",
            headers={
                "x-app-token": APP_TOKEN,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=5,
        )
        if not r.ok:
            logger.warning(f"SalesDoc sync failed [{r.status_code}]: {r.text[:200]}")
            return None
        result = r.json()
        logger.info(f"SalesDoc sync OK: row={row_num}, action={result.get('action')}")
        return result
    except requests.RequestException as e:
        logger.warning(f"SalesDoc sync exception: {e}")
        return None
