import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from services.sheets import get_payments_for_period
from keyboards.reports import reports_kb
from services.users import get_user_info

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "Otchety")
async def open_reports_menu(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    await message.answer("Vyberte tip otcheta:", reply_markup=reports_kb())


@router.message(F.text == "Za segodnya")
async def report_today(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    payments = get_payments_for_period(today, today)
    await message.answer(format_report(payments, "Za segodnya"))


@router.message(F.text == "Za nedelyu")
async def report_week(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today - timedelta(days=7)
    payments = get_payments_for_period(start, today)
    await message.answer(format_report(payments, "Za nedelyu"))


@router.message(F.text == "Za mesyats")
async def report_month(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    await message.answer(format_report(payments, "Za mesyats"))


@router.message(F.text == "Po menedzheram")
async def report_by_manager(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    await message.answer(format_report_by_manager(payments))


@router.message(F.text == "Po kategoriyam")
async def report_by_category(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    await message.answer(format_report_by_category(payments))


def format_report(payments: list, title: str) -> str:
    if not payments:
        return f"<b>{title}</b>\n\nOplat net."
    total = sum(p.get("amount", 0) for p in payments)
    lines = [f"<b>{title}</b>", f"Vsego oplat: {len(payments)}", f"Summa: {total:,} tg", ""]
    for p in payments[-10:]:
        lines.append(f"- {p.get('manager','?')} | {p.get('amount',0):,} tg | {p.get('status','?')}")
    return "\n".join(lines)


def format_report_by_manager(payments: list) -> str:
    if not payments:
        return "<b>Po menedzheram</b>\n\nOplat net."
    by_mgr = {}
    for p in payments:
        mgr = p.get("manager", "?")
        by_mgr.setdefault(mgr, {"count": 0, "total": 0})
        by_mgr[mgr]["count"] += 1
        by_mgr[mgr]["total"] += p.get("amount", 0)
    lines = ["<b>Po menedzheram (tekushiy mesyats)</b>", ""]
    for mgr, data in sorted(by_mgr.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"{mgr}: {data['count']} oplat | {data['total']:,} tg")
    return "\n".join(lines)


def format_report_by_category(payments: list) -> str:
    if not payments:
        return "<b>Po kategoriyam</b>\n\nOplat net."
    by_cat = {}
    for p in payments:
        cat = p.get("category", "?")
        by_cat.setdefault(cat, {"count": 0, "total": 0})
        by_cat[cat]["count"] += 1
        by_cat[cat]["total"] += p.get("amount", 0)
    lines = ["<b>Po kategoriyam (tekushiy mesyats)</b>", ""]
    for cat, data in sorted(by_cat.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"{cat}: {data['count']} oplat | {data['total']:,} tg")
    return "\n".join(lines)
