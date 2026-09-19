"""Outbound messages through the WhatsApp Cloud API (graph.facebook.com)."""

import hashlib
import hmac
import logging

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

MAX_TEXT = 4096  # WhatsApp text body limit

MENU_ROWS = [
    ("cmd_proposals", "Active proposals", "show active proposals"),
    ("cmd_treasury", "Treasury status", "treasury status"),
    ("cmd_votes", "Who hasn't voted?", "who hasn't voted?"),
    ("cmd_attack", "Run attack scan", "run attack scan"),
    ("cmd_balance", "My EDS balance", "check my EDS balance"),
    ("cmd_wallet", "Link wallet", "link wallet"),
]


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256. Skipped when no app secret is configured."""
    secret = get_settings().whatsapp_app_secret
    if not secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def _chunks(text: str) -> list[str]:
    if len(text) <= MAX_TEXT:
        return [text]
    parts, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > MAX_TEXT and current:
            parts.append(current)
            current = ""
        current += line
    parts.append(current)
    return [p[i : i + MAX_TEXT] for p in parts for i in range(0, len(p), MAX_TEXT)]


class WhatsAppClient:
    def __init__(self) -> None:
        s = get_settings()
        self._url = f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {s.whatsapp_access_token}"}
        self._http = httpx.AsyncClient(timeout=20)

    async def _post(self, payload: dict) -> bool:
        if not get_settings().whatsapp_enabled:
            # Demo mode: no Cloud API credentials, so treat the send as delivered and let the dashboard show it.
            log.info("WhatsApp not configured; simulated %s to %s", payload.get("type", "status"), payload.get("to"))
            return True
        try:
            resp = await self._http.post(
                self._url, headers=self._headers, json={"messaging_product": "whatsapp", **payload}
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as err:
            log.error("WhatsApp API %s: %s", err.response.status_code, err.response.text[:500])
        except httpx.HTTPError as err:
            log.error("WhatsApp request failed: %s", err)
        return False

    async def send_text(self, to: str, text: str) -> bool:
        ok = True
        for chunk in _chunks(text):
            ok &= await self._post(
                {"to": to, "type": "text", "text": {"body": chunk, "preview_url": True}}
            )
        if ok:
            log.info("Sent WhatsApp message to %s: %s", to, text[:80])
        return ok

    async def send_image(self, to: str, link: str, caption: str | None = None) -> bool:
        image = {"link": link, **({"caption": caption[:1024]} if caption else {})}
        return await self._post({"to": to, "type": "image", "image": image})

    async def send_menu(self, to: str) -> bool:
        return await self._post(
            {
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "header": {"type": "text", "text": "GovMind"},
                    "body": {"text": "Your DAO governance operator. Ask me anything, or pick a quick command:"},
                    "action": {
                        "button": "Commands",
                        "sections": [
                            {
                                "title": "Quick commands",
                                "rows": [{"id": rid, "title": title} for rid, title, _ in MENU_ROWS],
                            }
                        ],
                    },
                },
            }
        )

    async def mark_read(self, message_id: str) -> None:
        await self._post({"status": "read", "message_id": message_id})


_client: WhatsAppClient | None = None


def get_client() -> WhatsAppClient:
    global _client
    if _client is None:
        _client = WhatsAppClient()
    return _client
