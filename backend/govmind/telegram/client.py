"""Outbound messages through the Telegram Bot API.

Telegram members are stored with the id "tg:<chat id>" so they share the member
table, broadcast list and agent tools with WhatsApp members.
"""

import hashlib
import logging

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

PREFIX = "tg:"
MAX_TEXT = 4096
MAX_CAPTION = 1024

# Reply keyboard: tapping a button sends its text, so each one is a ready-made agent command.
KEYBOARD = [
    ["Is proposal 49 safe?", "Run attack scan"],
    ["Treasury status", "Who hasn't voted?"],
    ["Link wallet", "Check my EDS balance"],
]


def is_telegram(member_id: str) -> bool:
    return member_id.startswith(PREFIX)


def member_id(chat_id: int) -> str:
    return f"{PREFIX}{chat_id}"


def webhook_secret() -> str:
    """Secret Telegram echoes back in X-Telegram-Bot-Api-Secret-Token, derived from the bot token."""
    s = get_settings()
    return s.telegram_webhook_secret or hashlib.sha256(f"govmind:{s.telegram_bot_token}".encode()).hexdigest()[:32]


class TelegramClient:
    def __init__(self) -> None:
        self._base = f"https://api.telegram.org/bot{get_settings().telegram_bot_token}"
        self._http = httpx.AsyncClient(timeout=20)

    async def _call(self, method: str, payload: dict, quiet: bool = False) -> bool:
        if not get_settings().telegram_bot_token:
            log.info("Telegram not configured; simulated %s", method)
            return True
        try:
            resp = await self._http.post(f"{self._base}/{method}", json=payload)
            data = resp.json()
            if not data.get("ok"):
                if not quiet:
                    log.error("Telegram %s failed: %s", method, data.get("description"))
                return False
            return True
        except httpx.HTTPError as err:
            log.error("Telegram %s request failed: %s", method, err)
            return False

    async def send_text(self, to: str, text: str, keyboard: bool = False) -> bool:
        chat_id = to.removeprefix(PREFIX)
        ok = True
        for i in range(0, len(text), MAX_TEXT):
            payload: dict = {"chat_id": chat_id, "text": text[i : i + MAX_TEXT], "disable_web_page_preview": True}
            if keyboard and i == 0:
                payload["reply_markup"] = {"keyboard": [[{"text": t} for t in row] for row in KEYBOARD],
                                           "resize_keyboard": True}
            # The agent writes WhatsApp-style *bold*/_italic_, which Telegram's legacy Markdown also renders.
            # If an unbalanced marker makes Telegram reject it, resend as plain text.
            ok &= await self._call("sendMessage", {**payload, "parse_mode": "Markdown"}, quiet=True) or await self._call(
                "sendMessage", payload
            )
        return ok

    async def send_image(self, to: str, link: str, caption: str | None = None) -> bool:
        payload = {"chat_id": to.removeprefix(PREFIX), "photo": link}
        if caption:
            payload["caption"] = caption[:MAX_CAPTION]
        return await self._call("sendPhoto", payload)

    async def send_typing(self, to: str) -> None:
        await self._call("sendChatAction", {"chat_id": to.removeprefix(PREFIX), "action": "typing"})

    async def _get(self, method: str, payload: dict) -> dict | None:
        if not get_settings().telegram_bot_token:
            return None
        try:
            data = (await self._http.post(f"{self._base}/{method}", json=payload)).json()
            return data.get("result") if data.get("ok") else None
        except httpx.HTTPError:
            return None

    async def is_member(self, group: str, user: str) -> bool:
        """True if the user is in the group chat (so a group post already notifies them)."""
        result = await self._get(
            "getChatMember", {"chat_id": group.removeprefix(PREFIX), "user_id": int(user.removeprefix(PREFIX))}
        )
        return bool(result) and result.get("status") in ("creator", "administrator", "member", "restricted")

    async def bot_username(self) -> str | None:
        result = await self._get("getMe", {})
        return result.get("username") if result else None

    async def set_webhook(self, url: str) -> bool:
        return await self._call(
            "setWebhook",
            {
                "url": url,
                "secret_token": webhook_secret(),
                "allowed_updates": ["message", "my_chat_member"],
                "drop_pending_updates": True,
            },
        )

    async def set_menu_button(self, web_app_url: str) -> bool:
        """The bot's menu button opens the GovMind Mini App (the Telegram counterpart of the Luffa mini app)."""
        return await self._call(
            "setChatMenuButton",
            {"menu_button": {"type": "web_app", "text": "GovMind", "web_app": {"url": web_app_url}}},
        )


_client: TelegramClient | None = None


def get_client() -> TelegramClient:
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client
