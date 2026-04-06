# In-memory store for kassa notification message IDs
# Key: "rows:month", Value: [(chat_id, message_id), ...]
_store: dict[str, list[tuple[int, int]]] = {}


def save_messages(key: str, messages: list[tuple[int, int]]):
    """Save list of (chat_id, message_id) tuples for a planted key."""
    _store[key] = messages


def get_messages(key: str) -> list[tuple[int, int]]:
    """Get and remove stored messages for a key."""
    return _store.pop(key, [])
