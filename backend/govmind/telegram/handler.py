"""Turn inbound Telegram messages into agent runs."""

import logging

from ..services import governance
from ..whatsapp.handler import _already_seen, process_text
from .client import get_client, member_id
from .models import Update

log = logging.getLogger(__name__)

WELCOME = (
    "👋 Hi {name}, I'm GovMind, the governance operator for MetaDAO.\n\n"
    "You're now subscribed to DAO alerts: I'll message you here when I detect a governance attack, "
    "a suspicious proposal, or a treasury risk.\n\n"
    "Ask me anything about proposals, votes or the treasury, or tap a button below."
)


async def handle_update(update: Update) -> None:
    msg = update.message
    if not msg or not msg.text or msg.from_ is None:
        return
    if _already_seen(f"tg:{update.update_id}"):
        return
    sender = member_id(msg.chat.id)
    name = msg.from_.display_name
    text = msg.text.strip()
    tg = get_client()

    if text.startswith("/start") or text.lower() in {"/help", "menu", "help"}:
        await governance.track_group_member(sender, name)
        await tg.send_text(sender, WELCOME.format(name=name.split()[0]), keyboard=True)
        return

    await tg.send_typing(sender)
    await process_text(sender, name, text, channel="Telegram")
