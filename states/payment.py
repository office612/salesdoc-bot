from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    choose_manager       = State()
    choose_month         = State()
    choose_category      = State()
    choose_license       = State()
    enter_client         = State()
    enter_qty            = State()
    choose_period        = State()
    confirm_price        = State()
    enter_price          = State()
    enter_amount         = State()
    enter_manual_amount  = State()
    choose_bot_period    = State()
    enter_bot_amount     = State()
    choose_package       = State()
    choose_bank          = State()
    choose_service_bank  = State()  # 21.07.2026: услуги оплачивают в другой банк
    ask_add_service      = State()
    choose_payment_date  = State()
    enter_payment_date   = State()
    upload_receipt       = State()
    confirm              = State()


class AuthStates(StatesGroup):
    choosing_name = State()
