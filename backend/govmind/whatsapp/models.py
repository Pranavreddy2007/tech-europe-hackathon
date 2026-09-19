"""Pydantic models for the WhatsApp Cloud API webhook payload.

Only the fields GovMind uses are declared; everything else is ignored so new
Meta fields never break parsing.
"""

from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Profile(_M):
    name: str | None = None


class Contact(_M):
    wa_id: str
    profile: Profile | None = None


class TextBody(_M):
    body: str


class ReplyRef(_M):
    id: str
    title: str


class Interactive(_M):
    type: str
    button_reply: ReplyRef | None = None
    list_reply: ReplyRef | None = None


class QuickReplyButton(_M):
    text: str
    payload: str | None = None


class InboundMessage(_M):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: TextBody | None = None
    interactive: Interactive | None = None
    button: QuickReplyButton | None = None

    @property
    def body(self) -> str:
        """Plain text of the message, whatever kind of message it was."""
        if self.text:
            return self.text.body
        if self.interactive:
            reply = self.interactive.button_reply or self.interactive.list_reply
            return reply.title if reply else ""
        if self.button:
            return self.button.text
        return ""


class Metadata(_M):
    display_phone_number: str | None = None
    phone_number_id: str | None = None


class Value(_M):
    messaging_product: str | None = None
    metadata: Metadata | None = None
    contacts: list[Contact] = []
    messages: list[InboundMessage] = []


class Change(_M):
    field: str
    value: Value


class Entry(_M):
    id: str
    changes: list[Change] = []


class WebhookPayload(_M):
    object: str
    entry: list[Entry] = []

    def iter_messages(self):
        """Yield (message, sender display name) for every inbound user message."""
        for entry in self.entry:
            for change in entry.changes:
                if change.field != "messages":
                    continue
                names = {c.wa_id: c.profile.name if c.profile else None for c in change.value.contacts}
                for msg in change.value.messages:
                    yield msg, names.get(msg.from_)
