"""In-memory store: zvs_id → (chat_id, message_id) сообщения у заявителя.
При финализации (одобрено/отклонено/доработка) бот не шлёт новое сообщение,
а редактирует исходное. Один чат — одна заявка — одно сообщение.

При рестарте процесса dict теряется — fallback на send_message в этом случае."""

_messages: dict = {}  # {zvs_id: (chat_id, message_id)}


def save(zvs_id: int, chat_id: int, message_id: int):
    _messages[int(zvs_id)] = (int(chat_id), int(message_id))


def get(zvs_id: int):
    return _messages.get(int(zvs_id))
