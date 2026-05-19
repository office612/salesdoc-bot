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
# Чат операторов внедрения (Айдос/Акбар/Самат) — туда шлём уведомление о новом
# клиенте сразу как только бот создал карточку в SalesDoc. Без этого оператор
# узнаёт о клиенте только если сам зашёл в SalesDoc — это главная дыра процесса.
OPERATORS_CHAT_ID = os.getenv("OPERATORS_CHAT_ID", "")
BOT_TOKEN_NOTIFY = os.getenv("BOT_TOKEN", "")


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
        # После успешной синхронизации — уведомляем операторов о новой карточке.
        # Это закрывает главную дыру процесса: оператор узнаёт о клиенте сразу,
        # а не когда сам зайдёт в SalesDoc.
        try:
            notify_operators_new_card(payload, result)
        except Exception as _ne:
            logger.warning(f"Operators notify failed: {_ne}")
        return result
    except requests.RequestException as e:
        logger.warning(f"SalesDoc sync exception: {e}")
        return None


def notify_operators_new_card(payload: dict, sync_response: dict) -> None:
    """Шлёт сообщение в Telegram-чат операторов внедрения когда бот успешно создал
    новую карточку в SalesDoc Маршруте. Без кнопок (MVP) — просто текст, чтобы оператор
    зашёл в SalesDoc и взял клиента.

    payload — данные что мы отправляли в SalesDoc (категория, клиент, тариф, сумма)
    sync_response — ответ SalesDoc (action='card_created' | 'already_synced' | 'renewed' | ...)

    Молча пропускаем если:
      - env OPERATORS_CHAT_ID не настроен
      - не было создания карточки (например это продление абон.платы или дубль)
    """
    if not OPERATORS_CHAT_ID or not BOT_TOKEN_NOTIFY:
        return
    action = (sync_response or {}).get("action")
    # Уведомляем только когда карточка реально создалась — не при ignored / renewed / already_synced
    if action != "card_created":
        return

    company = payload.get("company") or "—"
    tariff = payload.get("tariff") or "—"
    amount = payload.get("amount") or 0
    manager = payload.get("manager") or "—"
    category = payload.get("category") or ""

    amount_str = f"{int(amount):,} ₸".replace(",", " ") if amount else "—"
    text_lines = [
        "<b>Новый клиент во Внедрение</b>",
        "",
        f"<b>{company}</b>",
        f"Категория: {category}",
        f"Тариф: {tariff}",
        f"Сумма: {amount_str}",
        f"Менеджер продаж: {manager}",
        "",
        "Кто берёт? Открой SalesDoc → Маршрут → колонка «Новый».",
    ]
    text = "\n".join(text_lines)

    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN_NOTIFY}/sendMessage",
            json={
                "chat_id": OPERATORS_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=5,
        )
        logger.info(f"Operators notified about {company}")
    except requests.RequestException as e:
        logger.warning(f"Telegram sendMessage failed: {e}")
