"""Realtime events for the dashboard over Socket.IO.

Event names are what `dashboard/lib/socket.ts` listens for.
"""

import json
import logging

import socketio

from .db import utcnow

log = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


def _now() -> str:
    return utcnow().isoformat()


async def agent_start(trigger: str) -> None:
    log.info("Agent started: %s", trigger[:80])
    await sio.emit("agent:start", {"trigger": trigger, "timestamp": _now()})


async def tool_start(tool: str, tool_input: dict) -> None:
    await sio.emit("agent:tool-start", {"tool": tool, "input": tool_input, "timestamp": _now()})


async def tool_result(tool: str, result: object) -> None:
    try:
        encoded = json.dumps(result, default=str)
        payload = result if len(encoded) <= 2000 else {"summary": encoded[:1900] + "...", "truncated": True}
    except (TypeError, ValueError):
        payload = {"summary": str(result)[:500], "truncated": True}
    await sio.emit("agent:tool-result", {"tool": tool, "result": payload, "timestamp": _now()})


async def agent_complete(response: str, steps: list[dict]) -> None:
    log.info("Agent complete: %s", response[:80])
    await sio.emit(
        "agent:complete",
        {
            "response": response,
            "steps": [{"tool": s["tool"], "description": s["description"]} for s in steps],
            "timestamp": _now(),
        },
    )


async def agent_error(error: str) -> None:
    log.error("Agent error: %s", error)
    await sio.emit("agent:error", {"error": error, "timestamp": _now()})


async def whatsapp_received(
    channel: str, text: str, sender: str | None = None, name: str | None = None, platform: str = "WhatsApp"
) -> None:
    await sio.emit(
        "whatsapp:message-received",
        {"type": channel, "text": text, "senderUid": sender, "senderName": name, "platform": platform,
         "timestamp": _now()},
    )


async def whatsapp_sent(
    channel: str,
    text: str,
    recipient: str | None = None,
    image_url: str | None = None,
    recipient_count: int = 1,
    platform: str | None = None,
) -> None:
    await sio.emit(
        "whatsapp:message-sent",
        {
            "type": channel,
            "text": text,
            "recipientUid": recipient,
            "imageUrl": image_url,
            "recipientCount": recipient_count,
            "platform": platform,
            "timestamp": _now(),
        },
    )
