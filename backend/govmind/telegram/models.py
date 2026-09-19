"""Pydantic models for the Telegram Bot API webhook payload (only the fields GovMind uses)."""

from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class User(_M):
    id: int
    first_name: str = ""
    last_name: str | None = None
    username: str | None = None

    @property
    def display_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p) or self.username or str(self.id)


class Chat(_M):
    id: int
    type: str


class Message(_M):
    message_id: int
    chat: Chat
    from_: User | None = Field(None, alias="from")
    text: str | None = None


class Update(_M):
    update_id: int
    message: Message | None = None
