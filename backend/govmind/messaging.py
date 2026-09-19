"""Route outbound messages to WhatsApp or Telegram based on the member id."""

from .telegram import client as telegram
from .whatsapp import client as whatsapp


def channel_of(member_id: str) -> str:
    return "telegram" if telegram.is_telegram(member_id) else "whatsapp"


async def deliver(to: str, text: str, image_url: str | None = None) -> bool:
    if telegram.is_telegram(to):
        tg = telegram.get_client()
        if image_url:
            await tg.send_image(to, image_url)
        return await tg.send_text(to, text)
    wa = whatsapp.get_client()
    if image_url:
        await wa.send_image(to, image_url)
    return await wa.send_text(to, text)
