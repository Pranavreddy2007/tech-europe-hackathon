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
    type: str  # private | group | supergroup | channel
    title: str | None = None

    @property
    def is_group(self) -> bool:
        return self.type in ("group", "supergroup")


class MessageEntity(_M):
    type: str  # mention | text_mention | bot_command | ...
    offset: int
    length: int
    user: User | None = None  # set for text_mention (mentions of users without a @username)


class Message(_M):
    message_id: int
    chat: Chat
    from_: User | None = Field(None, alias="from")
    text: str | None = None
    entities: list[MessageEntity] = []
    new_chat_members: list[User] = []


class ChatMember(_M):
    status: str  # creator | administrator | member | restricted | left | kicked
    user: User


class ChatMemberUpdated(_M):
    chat: Chat
    from_: User = Field(alias="from")
    new_chat_member: ChatMember


class Update(_M):
    update_id: int
    message: Message | None = None
    my_chat_member: ChatMemberUpdated | None = None  # the bot was added to / removed from a chat
