from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    choose_month       = State()
    choose_category    = State()
    choose_license     = State()
    enter_client       = State()
    enter_qty          = State()
    choose_period      = State()
    confirm_price      = State()   # НОВОЕ: подтвердить авто-цену или ввести вручную
    enter_price        = State()
    enter_amount       = State()
    choose_bank        = State()
    enter_fact         = State()
    choose_start_month = State()   # НОВОЕ: с какого месяца начинается оплата
    choose_activation  = State()   # НОВОЕ: активирован? (для нового клиента)
    choose_act_period  = State()   # НОВОЕ: период активации (10/20/полный)
    confirm            = State()


class AuthStates(StatesGroup):
    choosing_name = State()
