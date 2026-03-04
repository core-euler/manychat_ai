from __future__ import annotations

import httpx

from app.config import Settings


class ManyChatClient:
    def __init__(self, settings: Settings):
        self._base_url = settings.manychat_api_url.rstrip("/")
        self._token = settings.manychat_api_token
        self._send_flow_ns = settings.manychat_send_flow_ns
        self._field_ai_reply = settings.manychat_field_ai_reply
        self._field_handoff = settings.manychat_field_handoff

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def set_custom_field(self, subscriber_id: str, field_name: str, field_value: str) -> None:
        payload = {
            "subscriber_id": subscriber_id,
            "field_name": field_name,
            "field_value": field_value,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/fb/subscriber/setCustomField",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()

    async def save_reply_and_handoff(self, subscriber_id: str, reply_text: str, handoff: bool) -> None:
        await self.set_custom_field(subscriber_id, self._field_ai_reply, reply_text)
        await self.set_custom_field(subscriber_id, self._field_handoff, "true" if handoff else "false")

    async def send_flow(self, subscriber_id: str) -> None:
        payload = {
            "subscriber_id": subscriber_id,
            "flow_ns": self._send_flow_ns,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/fb/sending/sendFlow",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
