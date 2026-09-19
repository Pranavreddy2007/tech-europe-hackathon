"""Runtime state the bot learns and must keep across restarts (stored in the bot_state table)."""

from .config import get_settings
from .db import BotState, session_scope

TELEGRAM_GROUPS = "telegram_groups"
TELEGRAM_SUBSCRIBERS = "telegram_subscribers"


async def get_list(key: str) -> list[str]:
    async with session_scope() as s:
        row = await s.get(BotState, key)
        return list(row.value) if row else []


async def add_to_list(key: str, item: str) -> bool:
    """Add item if missing. Returns True when it was newly added."""
    async with session_scope() as s:
        row = await s.get(BotState, key)
        if row is None:
            s.add(BotState(key=key, value=[item]))
            return True
        if item in row.value:
            return False
        row.value = [*row.value, item]
        return True


async def remove_from_list(key: str, item: str) -> None:
    async with session_scope() as s:
        row = await s.get(BotState, key)
        if row and item in row.value:
            row.value = [v for v in row.value if v != item]


async def telegram_groups() -> list[str]:
    """Group chats GovMind posts to: learned from messages, plus TELEGRAM_GROUP_ID if set."""
    groups = await get_list(TELEGRAM_GROUPS)
    configured = get_settings().telegram_group_id
    if configured:
        configured_id = configured if configured.startswith("tg:") else f"tg:{configured}"
        groups = [configured_id, *[g for g in groups if g != configured_id]]
    return groups
