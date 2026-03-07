from __future__ import annotations

import logging
from pathlib import Path

from app.clients.comet import CometClient
from app.clients.manychat import ManyChatClient
from app.config import Settings
from app.db import add_message, get_recent_messages
from app.schemas import ManyChatWebhookIn
from app.services.followup_scheduler import schedule_followup_on_user_message

logger = logging.getLogger(__name__)
HANDOFF_TAG = "[HANDOFF]"
HANDOFF_PROMPT_RULE = (
    "If you need to hand off the user to a human admin for booking/scheduling/deposit, "
    "uncertain answers, or non-standard requests, end your reply with [HANDOFF]."
)


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


def load_system_prompt(path: str) -> str:
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"System prompt file is empty: {path}")

    if HANDOFF_TAG not in prompt:
        prompt = f"{prompt}\n\n{HANDOFF_PROMPT_RULE}"

    return prompt


async def process_incoming_message(payload: ManyChatWebhookIn, settings: Settings) -> None:
    try:
        channel = payload.channel.strip().lower()
        logger.info("Incoming message contact_id=%s channel=%s", payload.contact_id, channel)
        schedule_followup_on_user_message(settings, payload.contact_id, channel)

        history = get_recent_messages(settings.db_path, payload.contact_id, limit=30)
        add_message(settings.db_path, payload.contact_id, "user", payload.last_input)

        messages = [{"role": "system", "content": load_system_prompt(settings.system_prompt_path)}]
        messages.extend(history)
        messages.append({"role": "user", "content": payload.last_input})

        comet = CometClient(settings)
        llm_raw = await comet.complete(messages)

        reply_text, handoff = parse_handoff(llm_raw)
        reply_text = trim_for_channel(reply_text, channel)

        add_message(settings.db_path, payload.contact_id, "assistant", reply_text)

        manychat = ManyChatClient(settings)
        await manychat.save_reply_and_handoff(payload.contact_id, reply_text, handoff)
        flow_ns = manychat.resolve_reply_flow(channel)
        if not flow_ns:
            logger.warning(
                "Unsupported or unconfigured channel; sendFlow skipped contact_id=%s channel=%s",
                payload.contact_id,
                channel,
            )
            return

        logger.info(
            "Reply flow selected contact_id=%s channel=%s flow_ns=%s",
            payload.contact_id,
            channel,
            flow_ns,
        )
        await manychat.send_flow(payload.contact_id, flow_ns)
        logger.info(
            "sendFlow succeeded contact_id=%s channel=%s flow_ns=%s",
            payload.contact_id,
            channel,
            flow_ns,
        )

        logger.info(
            "Processed message contact_id=%s channel=%s handoff=%s",
            payload.contact_id,
            channel,
            handoff,
        )
    except Exception:
        logger.exception("Failed processing message for contact_id=%s", payload.contact_id)
