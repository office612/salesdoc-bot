import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from services.sheets import get_payments_for_period, get_sheet_by_month
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
    import calendar
    from datetime import datetime
    if year is None:
        year = date.today().year
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return get_payments_for_period(start, end)


def format_report(payments: list, title: str) -> str:
    if not payments:
        return f'📊 {title}: оплат нет.'
    total = sum(p.get('amount', 0) for p in payments)
    lines = [f'📊 <b>{title}</b>
']
    for i, p in enumerate(payments[:30], 1):
        dt = p.get('date', '')
        company = p.get('company', '—')
        mgr = p.get('manager', '—')
        amt = p.get('amount', 0)
        lines.append(f'{i}. {dt} | {company} | {mgr} | {amt:,.0f}')
    lines.append(f'
<b>Итого: {total:,.0f}</b> | Записей: {len(payments)}')
    if len(payments) > 30:
        lines.append(f'(Показано 30 из {len(payments)})')
    return '
'.join(lines)


@router.message(F.text == '📊 Отчёты')
async def open_reports_menu(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer('Не авторизован. /start')
        return
    await message.answer('📊 Выберите тип отчёта:', reply_markup=reports_kb())


@router.callback_query(F.data == 'report:today')
async def report_today(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    today = date.today()
    payments = get_payments_for_period(today, today)
    await callback.message.edit_text(format_report(payments, 'За сегодня'), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'report:week')
async def report_week(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    today = date.today()
    start = today - timedelta(days=7)
    payments = get_payments_for_period(start, today)
    await callback.message.edit_text(format_report(payments, 'За неделю'), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'report:pick_month')
async def pick_month(callback: CallbackQuery):
    await callback.message.edit_text('🗓 Выберите месяц:', reply_markup=months_kb())
    await callback.answer()


@router.callback_query(F.data.startswith('report:month:'))
async def report_by_month(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    month = int(callback.data.split(':')[2])
    month_name = MONTH_NAMES.get(month, str(month))
    payments = get_month_payments(month)
    await callback.message.edit_text(format_report(payments, month_name), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'report:managers')
async def report_by_manager(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    if not payments:
        await callback.message.edit_text('📊 Оплат нет за этот месяц.', reply_markup=back_to_reports_kb())
        await callback.answer()
        return
    by_mgr = {}
    for p in payments:
        m = p.get('manager', 'Неизвестно')
        by_mgr.setdefault(m, []).append(p)
    lines = ['📊 <b>По менеджерам (' + MONTH_NAMES.get(today.month,'') + ')</b>
']
    for mgr, plist in sorted(by_mgr.items()):
        total = sum(p.get('amount', 0) for p in plist)
        lines.append(f'👤 {mgr}: {len(plist)} оплат, <b>{total:,.0f}</b>')
    await callback.message.edit_text('
'.join(lines), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'report:categories')
async def report_by_category(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    if not payments:
        await callback.message.edit_text('📊 Оплат нет за этот месяц.', reply_markup=back_to_reports_kb())
        await callback.answer()
        return
    by_cat = {}
    for p in payments:
        c = p.get('category', 'Неизвестно')
        by_cat.setdefault(c, []).append(p)
    lines = ['📊 <b>По категориям (' + MONTH_NAMES.get(today.month,'') + ')</b>
']
    for cat, plist in sorted(by_cat.items()):
        total = sum(p.get('amount', 0) for p in plist)
        lines.append(f'📦 {cat}: {len(plist)} оплат, <b>{total:,.0f}</b>')
    await callback.message.edit_text('
'.join(lines), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'report:unseated')
async def report_unseated(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    unseated = [p for p in payments if str(p.get('seated','Net')).strip().lower() not in ('yes','da','ok')]
    await callback.message.edit_text(format_report(unseated, 'Не посаженные'), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'report:seated')
async def report_seated(callback: CallbackQuery):
    user = get_user_info(callback.from_user.id)
    if not user:
        await callback.answer('Не авторизован.', show_alert=True)
        return
    today = date.today()
    payments = get_month_payments(today.month)
    seated = [p for p in payments if str(p.get('seated','Net')).strip().lower() in ('yes','da','ok')]
    await callback.message.edit_text(format_report(seated, 'Посаженные'), reply_markup=back_to_reports_kb())
    await callback.answer()


@router.callback_query(F.data == 'back:reports')
async def back_to_reports(callback: CallbackQuery):
    await callback.message.edit_text('📊 Выберите тип отчёта:', reply_markup=reports_kb())
    await callback.answer()


@router.message(F.text == '⚠️ Не посаженные')
async def quick_unseated(message: Message):
    user = get_user_info(message.from_user.id)
    if not user:
        await message.answer('Не авторизован. /start')
        return
    today = date.today()
    payments = get_month_payments(today.month)
    unseated = [p for p in payments if str(p.get('seated','Net')).strip().lower() not in ('yes','da','ok')]
    await message.answer(format_report(unseated, 'Не посаженные'))
