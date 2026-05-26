"""Клавиатуры для ЗВС-бота."""

import os
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo,
)
from config import BANKS


def zvs_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню заявителя. Если задан ZVS_WEBAPP_URL — кнопка открывает форму."""
    webapp_url = os.getenv("ZVS_WEBAPP_URL", "").strip()
    if webapp_url:
        apply_btn = KeyboardButton(
            text="💸 Подать заявку",
            web_app=WebAppInfo(url=webapp_url),
        )
    else:
        apply_btn = KeyboardButton(text="💸 Подать заявку")
    return ReplyKeyboardMarkup(
        keyboard=[
            [apply_btn],
            [KeyboardButton(text="📋 Мои заявки")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def accounts_kb() -> InlineKeyboardMarkup:
    """Кнопки выбора счёта (тот же список что в @sakesdocbot)."""
    rows = []
    for b in BANKS:
        rows.append([InlineKeyboardButton(text=b.capitalize(), callback_data=f"zvs_acc:{b}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_apply_kb() -> InlineKeyboardMarkup:
    """Кнопки на шаге подтверждения заявки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="zvs_apply:send"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="zvs_apply:cancel"),
        ]
    ])


def director_decision_kb(zvs_id: int, applicant_uid: int) -> InlineKeyboardMarkup:
    """Кнопки директора под уведомлением о новой заявке."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"zvs_dec:ap:{zvs_id}:{applicant_uid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"zvs_dec:rj:{zvs_id}:{applicant_uid}"
            ),
            InlineKeyboardButton(
                text="🔄 Доработка",
                callback_data=f"zvs_dec:rw:{zvs_id}:{applicant_uid}"
            ),
        ]
    ])


def director_approve_kb(tg_id: int) -> InlineKeyboardMarkup:
    """Кнопки одобрения нового сотрудника директором."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Дать доступ", callback_data=f"zvs_reg:ok:{tg_id}"),
            InlineKeyboardButton(text="❌ Отказать", callback_data=f"zvs_reg:no:{tg_id}"),
        ]
    ])
