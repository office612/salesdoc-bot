from config import EMPLOYEES, LEADER
from services.sheets import get_user, register_user


def get_role(name: str) -> str:
    if name == LEADER:
        return "руководитель"
    if name in EMPLOYEES["managers"]:
        return "менеджер"
    if name in EMPLOYEES["accountants"]:
        return "бухгалтер"
    return "менеджер"


def get_all_names() -> list[str]:
    all_names = (
        EMPLOYEES["managers"]
        + EMPLOYEES["accountants"]
    )
    return all_names


def get_user_info(telegram_id: int) -> dict | None:
    return get_user(telegram_id)


def register(telegram_id: int, name: str) -> dict:
    role = get_role(name)
    register_user(telegram_id, name, role)
    return {"name": name, "role": role}


def is_manager(user: dict) -> bool:
    return user.get("role") in ("менеджер", "руководитель")


def is_accountant(user: dict) -> bool:
    return user.get("role") in ("бухгалтер", "руководитель")
