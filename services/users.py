from config import EMPLOYEES, LEADER
from services.sheets import get_user, register_user

# Маппинг старых английских имён на русские
LEGACY_NAMES = {
    'Mirzahait':   'Мирзахит',
    'Aidos':       'Мирзахит',
    'Aidos Hapez': 'Айдос Хапез',
    'Yulia':       'Юлия',
    'Akbar':       'Акбар',
    'Samat':       'Самат',
    'Gulshan':     'Гульшан',
    'Aurika':      'Аурика',
}


def get_role(name: str) -> str:
    if name == LEADER:
        return 'rukovoditel'
    if name in EMPLOYEES['managers']:
        return 'menedzher'
    if name in EMPLOYEES['accountants']:
        return 'buhgalter'
    return 'menedzher'


def get_all_names() -> list:
    return EMPLOYEES['managers'] + EMPLOYEES['accountants']


def get_user_info(telegram_id: int) -> dict | None:
    return get_user(telegram_id)


def register(telegram_id: int, name: str) -> dict:
    role = get_role(name)
    register_user(telegram_id, name, role)
    return {'name': name, 'role': role}


def fix_legacy_name(telegram_id: int, user: dict) -> dict:
    """Если имя старое (английское) — исправляем на русское и обновляем в таблице."""
    name = user.get('name', '')
    if name in LEGACY_NAMES:
        new_name = LEGACY_NAMES[name]
        new_role = get_role(new_name)
        register_user(telegram_id, new_name, new_role)
        user = dict(user)
        user['name'] = new_name
        user['role'] = new_role
    return user


def is_manager(user: dict) -> bool:
    return user.get('role') in ('menedzher', 'rukovoditel')


def is_accountant(user: dict) -> bool:
    return user.get('role') in ('buhgalter', 'rukovoditel')


def is_leader(user: dict) -> bool:
    return user.get('role') == 'rukovoditel'
