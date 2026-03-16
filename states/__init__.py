from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    choose_month    = State()
    choose_category = State()
    choose_license  = State()
    enter_client    = State()
    enter_qty       = State()
    choose_period   = State()
    enter_price     = State()
    enter_amount    = State()
    choose_bank     = State()
    enter_fact      = State()
    confirm         = State()


class AuthStates(StatesGroup):
    choosing_name = State()

