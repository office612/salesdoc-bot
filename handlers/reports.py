import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message
from services.sheets import get_payments_for_period
from keyboards.reports import reports_kb
from services.users import get_user_info

logger = logging.getLogger(__name__)
router = Router()


def format_report(payments: list, title: str) -> str:
    if not payments:
        return f"{title}: oplat net."
    total = sum(p.get('amount', 0) for p in payments)
    lines = [f"=== {title} ==="]
    for p in payments:
        lines.append(
            f"{p.get('date','')} | {p.get('manager','')} | {p.get('client','')} | {p.get('amount','')} | {p.get('status','')}"
        )
    lines.append(f"\nItogo: {total}")
    return "\n".join(lines)


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
    if not payments:
        await message.answer("Oplat net za etot mesyats.")
        return
    by_mgr = {}
    for p in payments:
        m = p.get('manager', 'Neizvestno')
        by_mgr.setdefault(m, []).append(p)
    lines = ["=== Po menedzheram (mesyats) ==="]
    for mgr, plist in by_mgr.items():
        total = sum(p.get('amount', 0) for p in plist)
        lines.append(f"{mgr}: {len(plist)} oplat, {total}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Po kategoriyam")
async def report_by_category(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    if not payments:
        await message.answer("Oplat net za etot mesyats.")
        return
    by_cat = {}
    for p in payments:
        c = p.get('category', 'Neizvestno')
        by_cat.setdefault(c, []).append(p)
    lines = ["=== Po kategoriyam (mesyats) ==="]
    for cat, plist in by_cat.items():
        total = sum(p.get('amount', 0) for p in plist)
        lines.append(f"{cat}: {len(plist)} oplat, {total}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Ne posazhenye")
async def report_unconfirmed(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    unconf = [p for p in payments if p.get('status', '').lower() not in ('podtverzhdeno', 'confirmed', 'ok')]
    await message.answer(format_report(unconf, "Ne posazhenye"))


@router.message(F.text == "Posazhenye")
async def report_confirmed(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    conf = [p for p in payments if p.get('status', '').lower() in ('podtverzhdeno', 'confirmed', 'ok')]
    await message.answer(format_report(conf, "Posazhenye"))
