from __future__ import annotations

import httpx

from app.config import Settings


class TelegramClient:
    def __init__(self, settings: Settings):
        self._bot_token = settings.telegram_bot_token
        self._admin_id = settings.telegram_admin_id

    @property
    def is_configured(self) -> bool:
        return bool(self._bot_token and self._admin_id)

    async def send_text(self, text: str) -> None:
        if not self.is_configured:
            return

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._admin_id,
            "text": text,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
