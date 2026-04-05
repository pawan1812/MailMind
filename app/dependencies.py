"""Session pool dependency — PRD §4.4."""

from typing import Dict
from app.core.environment import MailMindEnv

# Thread-safe pool: session_id -> MailMindEnv instance
_env_pool: Dict[str, MailMindEnv] = {}


def get_env(session_id: str = 'default') -> MailMindEnv:
    """Get or create a MailMindEnv for the given session."""
    if session_id not in _env_pool:
        _env_pool[session_id] = MailMindEnv(session_id=session_id)
    return _env_pool[session_id]


def remove_env(session_id: str):
    """Remove a session from the pool."""
    _env_pool.pop(session_id, None)


def list_sessions() -> list:
    """List all active session IDs."""
    return list(_env_pool.keys())
