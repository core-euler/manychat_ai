from __future__ import annotations

import logging
from pathlib import Path

from app.clients.comet import CometClient
from app.clients.manychat import ManyChatClient
from app.config import Settings
from app.db import add_message, get_recent_messages
from app.schemas import ManyChatWebhookIn

logger = logging.getLogger(__name__)
HANDOFF_TAG = "[HANDOFF]"


def channel_limit(channel: str) -> int:
    if channel.lower() == "instagram":
        return 1000
    return 2000


def trim_for_channel(text: str, channel: str) -> str:
    limit = channel_limit(channel)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def parse_handoff(text: str) -> tuple[str, bool]:
    if HANDOFF_TAG not in text:
        return text.strip(), False

    cleaned = text.replace(HANDOFF_TAG, "").strip()
    return cleaned, True


def load_system_prompt(path: str = "system_prompt.txt") -> str:
    prompt_path = Path(path)
    if not prompt_path.exists():
        logger.warning("system_prompt.txt not found, using fallback")
        return "You are a helpful AI sales assistant."
    return prompt_path.read_text(encoding="utf-8").strip()


async def process_incoming_message(payload: ManyChatWebhookIn, settings: Settings) -> None:
    try:
        add_message(settings.db_path, payload.contact_id, "user", payload.last_input)

        history = get_recent_messages(settings.db_path, payload.contact_id, limit=30)
        messages = [{"role": "system", "content": load_system_prompt()}]
        messages.extend(history)

        comet = CometClient(settings)
        llm_raw = await comet.complete(messages)

        reply_text, handoff = parse_handoff(llm_raw)
        reply_text = trim_for_channel(reply_text, payload.channel)

        add_message(settings.db_path, payload.contact_id, "assistant", reply_text)

        manychat = ManyChatClient(settings)
        await manychat.save_reply_and_handoff(payload.contact_id, reply_text, handoff)
        await manychat.send_flow(payload.contact_id)

        logger.info(
            "Processed message contact_id=%s channel=%s handoff=%s",
            payload.contact_id,
            payload.channel,
            handoff,
        )
    except Exception:
        logger.exception("Failed processing message for contact_id=%s", payload.contact_id)
