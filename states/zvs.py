"""FSM состояния для бота ЗВС (заявки на выдачу средств)."""

from aiogram.fsm.state import State, StatesGroup


class ZvsApply(StatesGroup):
    """Заполнение заявки: сумма + на что + счёт."""
    waiting_amount = State()
    waiting_purpose = State()
    waiting_account = State()
    waiting_confirm = State()


class ZvsDecision(StatesGroup):
    """Директор отклоняет/доработка — ждём комментарий."""
    waiting_reject_reason = State()
    waiting_rework_comment = State()
