from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    choose_category = State()
    choose_license = State()
    enter_client = State()
    choose_period = State()
    enter_amount = State()
    choose_bank = State()
    confirm = State()
