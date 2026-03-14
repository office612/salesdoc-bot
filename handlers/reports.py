import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from services.sheets import get_payments_for_period
from keyboards.reports import reports_kb, back_to_reports_kb
from services.users import get_user_info

logger = logging.getLogger(__name__)
router = Router()


def format_report(payments: list, title: str) -> str:
    if not payments:
        return f"📊 {title}: oplat net."
    total = sum(p.get('amount', 0) for p in payments)
    lines = [f"📊 <b>{title}</b>\n"]
    for i, p in enumerate(payments[:30], 1):
        lines.append(
            f"{i}. {p.get('date','')} | {p.get('company','')} | "
            f"{p.get('manager','')} | {p.get('amount', 0):,.0f}"
        )
    lines.append(f"\n<b>Itogo: {total:,.0f}</b>")
    if len(payments) > 30:
        lines.append(f"(Pokazano 30 iz {len(payments)})")
    return "\n".join(lines)


@router.message(F.text == "📊 Otchety")
async def open_reports_menu(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    await message.answer("📊 Vyberte tip otcheta:", reply_markup=reports_kb())


@router.callback_query(F.data == "report:today")
async def report_today(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    payments = get_payments_for_period(today, today)
    await callback.message.edit_text(format_report(payments, "Za segodnya"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:week")
async def report_week(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    start = today - timedelta(days=7)
    payments = get_payments_for_period(start, today)
    await callback.message.edit_text(format_report(payments, "Za nedelyu"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:month")
async def report_month(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    await callback.message.edit_text(format_report(payments, "Za mesyats"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:managers")
async def report_by_manager(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    if not payments:
        await callback.message.edit_text("📊 Oplat net za etot mesyats.", reply_markup=back_to_reports_kb())
        await callback.answer()
        return
    by_mgr = {}
    for p in payments:
        m = p.get('manager', 'Neizvestno')
        by_mgr.setdefault(m, []).append(p)
    lines = ["📊 <b>Po menedzheram (mesyats)</b>\n"]
    for mgr, plist in sorted(by_mgr.items()):
        total = sum(p.get('amount', 0) for p in plist)
        lines.append(f"👤 {mgr}: {len(plist)} oplat, <b>{total:,.0f}</b>")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:categories")
async def report_by_category(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    if not payments:
        await callback.message.edit_text("📊 Oplat net za etot mesyats.", reply_markup=back_to_reports_kb())
        await callback.answer()
        return
    by_cat = {}
    for p in payments:
        c = p.get('category', 'Neizvestno')
        by_cat.setdefault(c, []).append(p)
    lines = ["📊 <b>Po kategoriyam (mesyats)</b>\n"]
    for cat, plist in sorted(by_cat.items()):
        total = sum(p.get('amount', 0) for p in plist)
        lines.append(f"📦 {cat}: {len(plist)} oplat, <b>{total:,.0f}</b>")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:unseated")
async def report_unseated(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    unseated = [p for p in payments if str(p.get('seated', 'Net')).strip().lower() not in ('yes', 'da', 'ok', 'podtverzhdeno')]
    await callback.message.edit_text(format_report(unseated, "Ne posazhenye"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "report:seated")
async def report_seated(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer("Ne avtorizovan.", show_alert=True)
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    seated = [p for p in payments if str(p.get('seated', 'Net')).strip().lower() in ('yes', 'da', 'ok', 'podtverzhdeno')]
    await callback.message.edit_text(format_report(seated, "Posazhenye"), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == "back:reports")
async def back_to_reports(callback: CallbackQuery):
    await callback.message.edit_text("📊 Vyberte tip otcheta:", reply_markup=reports_kb())
    await callback.answer()


@router.message(F.text == "⚠️ Ne posazhenye")
async def quick_unseated(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer("Ne avtorizovan. /start")
        return
    today = date.today()
    start = today.replace(day=1)
    payments = get_payments_for_period(start, today)
    unseated = [p for p in payments if str(p.get('seated', 'Net')).strip().lower() not in ('yes', 'da', 'ok', 'podtverzhdeno')]
    await message.answer(format_report(unseated, "Ne posazhenye"))
