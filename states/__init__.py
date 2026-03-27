from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    choose_manager = State()
    choose_month = State()
    choose_category = State()
    choose_license = State()
    enter_client = State()
    enter_qty = State()
    choose_period = State()
    choose_package = State()
    choose_payment_date = State()
    enter_payment_date  = State()
    confirm_price = State()
    enter_price = State()
    enter_amount = State()
    choose_bank = State()
    enter_fact = State()
    choose_start_month = State()
    choose_activation  = State()
    choose_act_period  = State()
    confirm            = State()
    upload_receipt  = State()


class AuthStates(StatesGroup):
    choosing_name = State()
