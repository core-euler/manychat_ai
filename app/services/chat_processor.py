from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.clients.comet import CometClient
from app.clients.manychat import ManyChatClient
from app.clients.telegram import TelegramClient
from app.config import Settings
from app.db import (
    activate_handoff,
    add_message,
    get_recent_messages,
    is_handoff_active,
    register_handoff_notification,
)
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


def _extract_city(payload: ManyChatWebhookIn, history: list[dict[str, str]]) -> str:
    if payload.city:
        return payload.city.strip()

    city_aliases = {
        "будва": "Будва",
        "budva": "Budva",
        "подгорица": "Подгорица",
        "podgorica": "Podgorica",
    }
    for msg in reversed(history):
        content = (msg.get("content") or "").lower()
        for alias, normalized in city_aliases.items():
            if alias in content:
                return normalized
    return "не указано"


def _extract_date(payload: ManyChatWebhookIn, history: list[dict[str, str]]) -> str:
    if payload.date:
        return payload.date.strip()

    date_markers = [
        "сегодня",
        "завтра",
        "послезавтра",
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
        "today",
        "tomorrow",
        "next week",
    ]
    for msg in reversed(history):
        content = (msg.get("content") or "").strip()
        low = content.lower()
        for marker in date_markers:
            if marker in low:
                return content
    return "не указано"


def _build_name(payload: ManyChatWebhookIn) -> str:
    parts = [p.strip() for p in [payload.first_name, payload.last_name] if p and p.strip()]
    if parts:
        return " ".join(parts)
    return "не указано"


def _normalize_username(value: str | None) -> str:
    if not value or not value.strip():
        return "не указано"
    username = value.strip()
    if username.startswith("@"):
        return username
    return f"@{username}"


def _is_admin_handoff_signal(handoff: bool, reply_text: str) -> bool:
    if handoff:
        return True
    low = reply_text.lower()
    markers = [
        "передам информацию",
        "передам мастеру",
        "передам администратору",
        "i will pass",
        "i'll pass",
    ]
    return any(marker in low for marker in markers)


def _build_telegram_message(
    name: str,
    username: str,
    city: str,
    date: str,
    channel: str,
) -> str:
    return (
        "Новый клиент готов записаться\n\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"Город: {city}\n"
        f"Дата: {date}\n"
        f"Соцсеть: {channel}"
    )


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

        reply_text, handoff_detected = parse_handoff(llm_raw)
        reply_text = trim_for_channel(reply_text, channel)

        add_message(settings.db_path, payload.contact_id, "assistant", reply_text)

        handoff_active_before = is_handoff_active(settings.db_path, payload.contact_id)
        handoff_to_write = False
        handoff_active_after = handoff_active_before
        if handoff_detected:
            logger.info("handoff detected contact_id=%s", payload.contact_id)
            if handoff_active_before:
                logger.info("handoff already active contact_id=%s", payload.contact_id)
            else:
                if activate_handoff(settings.db_path, payload.contact_id):
                    handoff_to_write = True
                    handoff_active_after = True
                    logger.info("handoff flag updated to true contact_id=%s", payload.contact_id)
                else:
                    handoff_active_after = True
                    logger.info("handoff already active contact_id=%s", payload.contact_id)
        else:
            logger.info(
                "handoff flag preserved contact_id=%s active=%s",
                payload.contact_id,
                handoff_active_before,
            )

        manychat = ManyChatClient(settings)
        await manychat.save_reply_and_handoff(payload.contact_id, reply_text, handoff_to_write)
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

        if _is_admin_handoff_signal(handoff_detected, reply_text):
            dedupe_source = f"{channel}|{payload.last_input.strip().lower()}|{reply_text.strip().lower()}"
            dedupe_key = hashlib.sha256(dedupe_source.encode("utf-8")).hexdigest()
            if register_handoff_notification(settings.db_path, payload.contact_id, dedupe_key):
                telegram = TelegramClient(settings)
                if telegram.is_configured:
                    conversation_for_extract = history + [{"role": "user", "content": payload.last_input}]
                    name = _build_name(payload)
                    username = _normalize_username(payload.username)
                    city = _extract_city(payload, conversation_for_extract)
                    date = _extract_date(payload, conversation_for_extract)
                    telegram_text = _build_telegram_message(name, username, city, date, channel)
                    try:
                        await telegram.send_text(telegram_text)
                        logger.info("telegram_notification_sent contact_id=%s", payload.contact_id)
                    except Exception:
                        logger.exception("telegram_notification_failed contact_id=%s", payload.contact_id)
                else:
                    logger.warning("telegram_notification_skipped_not_configured contact_id=%s", payload.contact_id)
            else:
                logger.info("telegram_notification_skipped_duplicate contact_id=%s", payload.contact_id)

        logger.info(
            "Processed message contact_id=%s channel=%s handoff_detected=%s handoff_active=%s",
            payload.contact_id,
            channel,
            handoff_detected,
            handoff_active_after,
        )
    except Exception:
        logger.exception("Failed processing message for contact_id=%s", payload.contact_id)
