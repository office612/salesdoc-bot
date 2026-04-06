"""In-memory store for kassa notification message IDs."""

_store = {}


def save_messages(key, messages):
    """Save list of (chat_id, message_id) tuples for a planted key."""
    _store[key] = messages


def get_messages(key):
    """Get and remove stored messages for a key."""
    return _store.pop(key, [])
