from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0


class ManyChatClient:
    def __init__(self, settings: Settings):
        self._base_url = settings.manychat_api_url.rstrip("/")
        self._token = settings.manychat_api_token
        self._flow_map = {
            "instagram": settings.manychat_reply_flow_instagram,
            "facebook": settings.manychat_reply_flow_facebook,
            "whatsapp": settings.manychat_reply_flow_whatsapp,
        }
        self._followup_flow_map = {
            "instagram": settings.manychat_followup_flow_instagram,
            "facebook": settings.manychat_followup_flow_facebook,
            "whatsapp": settings.manychat_followup_flow_whatsapp,
        }
        self._fallback_flow_ns = settings.manychat_send_flow_ns
        self._field_ai_reply = settings.manychat_field_ai_reply
        self._field_ai_followup = settings.manychat_field_ai_followup
        self._field_handoff = settings.manychat_field_handoff

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _post_with_retry(self, endpoint: str, payload: dict) -> None:
        url = f"{self._base_url}{endpoint}"

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        url,
                        headers=self._headers,
                        json=payload,
                    )
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"ManyChat server error {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
                if attempt >= RETRY_ATTEMPTS:
                    raise
                delay = RETRY_BASE_DELAY_SECONDS * attempt
                logger.warning(
                    "ManyChat network error, retrying attempt=%s/%s endpoint=%s delay=%.1fs error=%s",
                    attempt,
                    RETRY_ATTEMPTS,
                    endpoint,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code is None or status_code < 500 or attempt >= RETRY_ATTEMPTS:
                    raise
                delay = RETRY_BASE_DELAY_SECONDS * attempt
                logger.warning(
                    "ManyChat 5xx error, retrying attempt=%s/%s endpoint=%s status=%s delay=%.1fs",
                    attempt,
                    RETRY_ATTEMPTS,
                    endpoint,
                    status_code,
                    delay,
                )
                await asyncio.sleep(delay)

    async def set_custom_field(self, subscriber_id: str, field_name: str, field_value: str) -> None:
        payload = {
            "subscriber_id": subscriber_id,
            "field_name": field_name,
            "field_value": field_value,
        }
        await self._post_with_retry("/fb/subscriber/setCustomFieldByName", payload)

    async def save_reply_and_handoff(self, subscriber_id: str, reply_text: str, handoff: bool) -> None:
        await self.set_custom_field(subscriber_id, self._field_ai_reply, reply_text)
        if handoff:
            await self.set_custom_field(subscriber_id, self._field_handoff, "true")

    async def save_followup_reply(self, subscriber_id: str, followup_text: str) -> None:
        await self.set_custom_field(subscriber_id, self._field_ai_followup, followup_text)

    def resolve_reply_flow(self, channel: str) -> str | None:
        normalized = channel.strip().lower()
        if normalized not in self._flow_map:
            return None

        flow_ns = self._flow_map.get(normalized)
        if flow_ns:
            return flow_ns

        return self._fallback_flow_ns

    def resolve_followup_flow(self, channel: str) -> str | None:
        normalized = channel.strip().lower()
        return self._followup_flow_map.get(normalized)

    async def send_flow(self, subscriber_id: str, flow_ns: str) -> None:
        payload = {
            "subscriber_id": subscriber_id,
            "flow_ns": flow_ns,
        }
        await self._post_with_retry("/fb/sending/sendFlow", payload)
