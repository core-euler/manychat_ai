from __future__ import annotations

import httpx

from app.config import Settings


class CometClient:
    def __init__(self, settings: Settings):
        self._base_url = settings.comet_api_url.rstrip("/")
        self._api_key = settings.comet_api_key
        self._model = settings.comet_model
        self._max_tokens = settings.comet_max_tokens

    def _build_payload(self, messages: list[dict[str, str]]) -> dict:
        payload: dict = {
            "model": self._model,
            "messages": messages,
        }
        # CometAPI docs note GPT-5 variants may expect max_completion_tokens.
        if self._model.startswith("gpt-5") and self._model != "gpt-5-chat-latest":
            payload["max_completion_tokens"] = self._max_tokens
        else:
            payload["max_tokens"] = self._max_tokens
        return payload

    async def complete(self, messages: list[dict[str, str]]) -> str:
        payload = self._build_payload(messages)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError("CometAPI returned no choices")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("CometAPI returned empty content")

        return content.strip()
