from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    company      = State()
    category     = State()
    license_type = State()
    license_qty  = State()
    license_rate = State()
    period       = State()
    amount       = State()
    impl_amount  = State()
    bank         = State()
    screenshot   = State()
    comment      = State()
    confirm      = State()


class AuthStates(StatesGroup):
    choose_name = State()
