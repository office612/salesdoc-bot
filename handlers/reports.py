import logging
import calendar
from datetime import date, timedelta, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from config import CURRENCY
from services.sheets import get_payments_for_period
from keyboards.reports import reports_kb, back_to_reports_kb, months_kb
from services.users import get_user_info

logger = logging.getLogger(__name__)
router = Router()

MONTH_NAMES = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}


def get_month_payments(month: int, year: int = None) -> list:
    if year is None:
        year = date.today().year
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return get_payments_for_period(start, end)


def format_report(payments: list, title: str) -> str:
    if not payments:
        return "<b>" + title + "</b>\n\nОплат нет."
    total = sum(p.get("amount", 0) for p in payments)
    lines = ["<b>" + title + "</b>\n"]
    for i, p in enumerate(payments, 1):
        dt = str(p.get("date", ""))
        company = p.get("company", "—")
        mgr = p.get("manager", "—")
        amt = p.get("amount", 0)
        lines.append(
            str(i) + ". " + dt + " | " + company + " | " + mgr + " | "
            + "{:,.0f}".format(amt).replace(",", " ")
        )
    lines.append("\n<b>Итого: " + "{:,.0f}".format(total).replace(",", " ") + " " + CURRENCY + "</b> | Записей: " + str(len(payments)))
    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4090] + "\n..."
    return text


@router.message(F.text == "📊 Отчёты")
async def open_reports_menu(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Не авторизован. /start")
        return
    await message.answer("Выберите тип отчёта:", reply_markup=reports_kb())


@router.callback_query(F.data == "report:today")
async def report_today(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    today = date.today()
    payments = get_payments_for_period(today, today)
    await callback.message.edit_text(format_report(payments, "За сегодня"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:week")
async def report_week(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    today = date.today()
    start = today - timedelta(days=7)
    payments = get_payments_for_period(start, today)
    await callback.message.edit_text(format_report(payments, "За неделю"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:pick_month")
async def pick_month(callback: CallbackQuery):
    await callback.message.edit_text("Выберите месяц:", reply_markup=months_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("report:month:"))
async def report_by_month(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    month = int(callback.data.split(":")[2])
    month_name = MONTH_NAMES.get(month, str(month))
    payments = get_month_payments(month)
    await callback.message.edit_text(format_report(payments, month_name), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:managers")
async def report_by_manager(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    if not payments:
        await callback.message.edit_text("Оплат нет за этот месяц.", reply_markup=back_to_reports_kb())
        await callback.answer()
        return
    by_mgr = {}
    for p in payments:
        m = p.get("manager", "Неизвестно")
        by_mgr.setdefault(m, []).append(p)
    lines = ["<b>По менеджерам (" + MONTH_NAMES.get(today.month, "") + ")</b>\n"]
    for mgr, plist in sorted(by_mgr.items()):
        total = sum(p.get("amount", 0) for p in plist)
        lines.append(mgr + ": " + str(len(plist)) + " оплат — <b>" + "{:,.0f}".format(total).replace(",", " ") + " " + CURRENCY + "</b>")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:categories")
async def report_by_category(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    if not payments:
        await callback.message.edit_text("Оплат нет за этот месяц.", reply_markup=back_to_reports_kb())
        await callback.answer()
        return
    by_cat = {}
    for p in payments:
        c = p.get("category", "Неизвестно")
        by_cat.setdefault(c, []).append(p)
    lines = ["<b>По статьям (" + MONTH_NAMES.get(today.month, "") + ")</b>\n"]
    for cat, plist in sorted(by_cat.items()):
        total = sum(p.get("amount", 0) for p in plist)
        lines.append(cat + ": " + str(len(plist)) + " оплат — <b>" + "{:,.0f}".format(total).replace(",", " ") + " " + CURRENCY + "</b>")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:unseated")
async def report_unseated(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    unseated = [p for p in payments if str(p.get("seated", "Нет")).strip().lower() not in ("да", "yes", "ok")]
    await callback.message.edit_text(format_report(unseated, "Не посаженные"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:seated")
async def report_seated(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Не авторизован.", show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    seated = [p for p in payments if str(p.get("seated", "Нет")).strip().lower() in ("да", "yes", "ok")]
    await callback.message.edit_text(format_report(seated, "Посаженные"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "back:reports")
async def back_to_reports(callback: CallbackQuery):
    await callback.message.edit_text("Выберите тип отчёта:", reply_markup=reports_kb())
    await callback.answer()


@router.message(F.text == "⚠️ Не посаженные")
async def quick_unseated(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Не авторизован. /start")
        return
    today = date.today()
    payments = get_month_payments(today.month)
    unseated = [p for p in payments if str(p.get("seated", "Нет")).strip().lower() not in ("да", "yes", "ok")]
    await message.answer(format_report(unseated, "Не посаженные"))
