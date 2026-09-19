"""Turn inbound Telegram messages into agent runs.

Private chats work like WhatsApp: /start subscribes you to DAO alerts and GovMind replies to you.
Group chats work like the original Luffa group: GovMind learns the group, tracks members and
@mentions, auto-links wallets posted in chat, and answers in the group.
"""

import logging

from .. import state
from ..services import governance
from ..whatsapp.handler import _already_seen, _track, process_text
from .client import get_client, member_id
from .models import Message, Update

log = logging.getLogger(__name__)

WELCOME = (
    "👋 Hi {name}, I'm GovMind, the governance operator for MetaDAO.\n\n"
    "You're now subscribed to DAO alerts: I'll message you here when I detect a governance attack, "
    "a suspicious proposal, or a treasury risk.\n\n"
    "Ask me anything about proposals, votes or the treasury, or tap a button below."
)

GROUP_WELCOME = (
    "👋 GovMind is now active in {title}.\n\n"
    "I'll post proposal briefings, vote reminders, treasury alerts and governance-attack alerts here. "
    "Mention me (@{bot}) or reply to my messages to ask anything about the DAO."
)


async def _learn_group(chat_id: int, title: str | None) -> None:
    group = member_id(chat_id)
    if await state.add_to_list(state.TELEGRAM_GROUPS, group):
        log.info("Learned Telegram group %s (%s)", group, title)
        bot = await get_client().bot_username() or "GovMind_bot"
        await get_client().send_text(group, GROUP_WELCOME.format(title=title or "this group", bot=bot))


async def _track_mentions(msg: Message) -> None:
    for entity in msg.entities:
        if entity.type == "text_mention" and entity.user and not entity.user.id == (msg.from_.id if msg.from_ else 0):
            try:
                await governance.track_group_member(member_id(entity.user.id), entity.user.display_name)
            except Exception:
                log.exception("Mention tracking failed")


async def handle_update(update: Update) -> None:
    if _already_seen(f"tg:{update.update_id}"):
        return

    # Bot added to (or removed from) a group.
    if cm := update.my_chat_member:
        if cm.chat.is_group:
            if cm.new_chat_member.status in ("member", "administrator"):
                await _learn_group(cm.chat.id, cm.chat.title)
            elif cm.new_chat_member.status in ("left", "kicked"):
                await state.remove_from_list(state.TELEGRAM_GROUPS, member_id(cm.chat.id))
        return

    msg = update.message
    if not msg or msg.from_ is None:
        return
    tg = get_client()

    if msg.chat.is_group:
        await _learn_group(msg.chat.id, msg.chat.title)
        sender = member_id(msg.from_.id)
        for user in msg.new_chat_members:
            await governance.track_group_member(member_id(user.id), user.display_name)
        if not msg.text:
            return
        await _track_mentions(msg)
        text = msg.text.strip()
        if text.startswith("/start") or text.startswith("/help"):
            await _track(sender, msg.from_.display_name, text)
            await tg.send_text(member_id(msg.chat.id), GROUP_WELCOME.format(
                title=msg.chat.title or "this group", bot=await tg.bot_username() or "GovMind_bot"))
            return
        await tg.send_typing(member_id(msg.chat.id))
        await process_text(sender, msg.from_.display_name, text, channel="Telegram group",
                           group_id=member_id(msg.chat.id))
        return

    if not msg.text:
        return
    sender = member_id(msg.chat.id)
    name = msg.from_.display_name
    text = msg.text.strip()

    if text.startswith("/start") or text.lower() in {"/help", "menu", "help"}:
        await governance.track_group_member(sender, name)
        await state.add_to_list(state.TELEGRAM_SUBSCRIBERS, sender)
        await tg.send_text(sender, WELCOME.format(name=name.split()[0]), keyboard=True)
        return

    await state.add_to_list(state.TELEGRAM_SUBSCRIBERS, sender)
    await tg.send_typing(sender)
    await process_text(sender, name, text, channel="Telegram")
