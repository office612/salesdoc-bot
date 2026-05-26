"""Хранилище пользователей, ожидающих одобрения от директора.

Простое in-memory. При перезапуске Railway сбрасывается — директор
заметит, юзер пришлёт /start ещё раз.
"""

_pending = {}  # {telegram_id: {"name": str, "username": str}}


def add(telegram_id: int, name: str, username: str = ""):
    _pending[telegram_id] = {"name": name, "username": username}


def get(telegram_id: int):
    return _pending.get(telegram_id)


def remove(telegram_id: int):
    _pending.pop(telegram_id, None)
