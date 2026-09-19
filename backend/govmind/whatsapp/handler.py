"""Turn inbound WhatsApp messages into agent runs."""

import logging
import re
import time
from collections import OrderedDict, deque

from .. import events
from ..agent import runner
from ..agent.tools import RunContext
from ..services import governance
from .client import MENU_ROWS, get_client
from .models import InboundMessage

log = logging.getLogger(__name__)

MAX_HISTORY = 20
MAX_SEEN = 10_000
MENU_COMMANDS = {rid: command for rid, _, command in MENU_ROWS}
MENU_TRIGGERS = {"menu", "help", "commands", "/start", "start"}

HEX_ADDRESS = re.compile(r"\b(0x[a-fA-F0-9]{64})\b")
BASE58_ADDRESS = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")
WALLET_CONTEXT = re.compile(r"wallet|address|link", re.IGNORECASE)

# Meta retries webhooks, so the same message id can arrive more than once.
_seen: OrderedDict[str, None] = OrderedDict()
_history: dict[str, deque[tuple[str, str, float]]] = {}


def reset_state() -> None:
    _seen.clear()
    _history.clear()


def _already_seen(message_id: str) -> bool:
    if message_id in _seen:
        return True
    _seen[message_id] = None
    if len(_seen) > MAX_SEEN:
        _seen.popitem(last=False)
    return False


def message_text(msg: InboundMessage) -> str:
    if msg.interactive:
        reply = msg.interactive.list_reply or msg.interactive.button_reply
        if reply and reply.id in MENU_COMMANDS:
            return MENU_COMMANDS[reply.id]
    return msg.body.strip()


def extract_wallet(text: str) -> str | None:
    if m := HEX_ADDRESS.search(text):
        return m.group(1)
    if WALLET_CONTEXT.search(text) and (m := BASE58_ADDRESS.search(text)):
        return m.group(1)
    return None


async def handle_message(msg: InboundMessage, sender_name: str | None) -> None:
    """Inbound WhatsApp message."""
    if _already_seen(msg.id):
        return
    sender = msg.from_
    text = message_text(msg)
    wa = get_client()
    await wa.mark_read(msg.id)

    if not text:
        await wa.send_text(sender, "I can only read text messages for now. Send \"menu\" to see what I can do.")
        return
    if text.lower() in MENU_TRIGGERS:
        await _track(sender, sender_name, text)
        await wa.send_menu(sender)
        return
    await process_text(sender, sender_name, text, channel="WhatsApp")


async def _track(sender: str, sender_name: str | None, text: str) -> None:
    try:
        await governance.track_group_member(sender, sender_name)
        if wallet := extract_wallet(text):
            await governance.link_wallet(sender, wallet)
            log.info("Auto-linked wallet %s... for %s", wallet[:10], sender)
    except Exception:  # tracking is best-effort; never block the reply
        log.exception("Member tracking failed")


async def process_text(sender: str, sender_name: str | None, text: str, channel: str) -> None:
    """Channel-agnostic core: track the member, show the message on the dashboard, run the agent."""
    log.info("%s message from %s: %s", channel, sender, text[:100])
    await events.whatsapp_received("dm", text, sender, sender_name, platform=channel)
    await _track(sender, sender_name, text)

    history = _history.setdefault(sender, deque(maxlen=MAX_HISTORY))
    history.append((sender_name or sender, text, time.time()))

    member = await governance.get_group_member(sender)
    info = [f"- Member ID: {sender} ({channel})"]
    if member and member.display_name:
        info.append(f"- Display name: {member.display_name}")
    if member and member.wallet_address:
        info.append(f"- Linked wallet: {member.wallet_address} (already linked, do NOT ask for it again)")
    else:
        info.append("- Wallet: not linked yet")

    recent = list(history)[-10:]
    conversation = ""
    if len(recent) > 1:
        lines = "\n".join(f"[{who}]: {said}" for who, said, _ in recent)
        conversation = f"\n\nRecent conversation with this member (use it for follow-ups):\n{lines}\n---"

    trigger = (
        f'A DAO member sent you this {channel} message: "{text}"\n\nSender info:\n'
        + "\n".join(info)
        + conversation
        + "\n\nRespond helpfully. If it's a question, answer it using the available tools. If it's a correction "
        "or definition, store it. Check the knowledge base for relevant corrections before answering. Reply to "
        "the member with send_direct_message (no whatsapp_id needed). Broadcast with send_group_message only if "
        "the whole DAO needs to see it."
    )
    await runner.run(trigger, RunContext(sender_id=sender))
    history.append(("GovMind", "[responded]", time.time()))
