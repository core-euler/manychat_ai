from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.clients.comet import CometClient
from app.clients.manychat import ManyChatClient
from app.config import Settings
from app.db import (
    add_message,
    claim_followup_for_sending,
    get_due_followups,
    get_followup_state,
    get_recent_messages,
    requeue_stale_sending_followups,
    update_followup_status,
    upsert_followup_state,
)

logger = logging.getLogger(__name__)

FOLLOWUP_DELAY = timedelta(hours=6)
FOLLOWUP_MAX_AGE = timedelta(days=14)
FOLLOWUP_RETRY_DELAY = timedelta(minutes=15)
FOLLOWUP_POLL_INTERVAL_SECONDS = 30
FOLLOWUP_SENDING_STALE_AFTER = timedelta(minutes=10)
SUPPORTED_CHANNELS = {"instagram", "facebook", "whatsapp"}
FOLLOWUP_HISTORY_LIMIT = 20
HANDOFF_TAG = "[HANDOFF]"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _load_system_prompt(path: str) -> str:
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"System prompt file is empty: {path}")
    return prompt


def _trim_for_channel(text: str, channel: str) -> str:
    limit = 1000 if channel == "instagram" else 2000
    clean = text.strip().replace(HANDOFF_TAG, "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


async def _generate_followup_text(settings: Settings, contact_id: str, channel: str) -> str:
    history = get_recent_messages(settings.db_path, contact_id, limit=FOLLOWUP_HISTORY_LIMIT)
    messages: list[dict[str, str]] = [{"role": "system", "content": _load_system_prompt(settings.system_prompt_path)}]
    messages.extend(history)
    messages.append({"role": "user", "content": _load_system_prompt(settings.followup_prompt_path)})

    comet = CometClient(settings)
    raw_text = await comet.complete(messages)
    return _trim_for_channel(raw_text, channel)


def schedule_followup_on_user_message(settings: Settings, contact_id: str, channel: str) -> None:
    now = _utcnow()
    normalized_channel = channel.strip().lower()
    previous_state = get_followup_state(settings.db_path, contact_id)

    if normalized_channel not in SUPPORTED_CHANNELS:
        upsert_followup_state(
            settings.db_path,
            contact_id=contact_id,
            channel=normalized_channel,
            last_user_message_at=_iso(now),
            scheduled_from_message_at=_iso(now),
            followup_scheduled_for=None,
            status="unsupported_channel",
        )
        logger.warning(
            "Follow-up unsupported channel contact_id=%s channel=%s",
            contact_id,
            normalized_channel,
        )
        return

    scheduled_for = now + FOLLOWUP_DELAY
    upsert_followup_state(
        settings.db_path,
        contact_id=contact_id,
        channel=normalized_channel,
        last_user_message_at=_iso(now),
        scheduled_from_message_at=_iso(now),
        followup_scheduled_for=_iso(scheduled_for),
        status="scheduled",
    )
    if previous_state and previous_state.get("followup_scheduled_for"):
        logger.info(
            "Follow-up skipped because user replied contact_id=%s channel=%s previous_scheduled_for=%s",
            contact_id,
            normalized_channel,
            previous_state.get("followup_scheduled_for"),
        )
    logger.info(
        "Follow-up scheduled contact_id=%s channel=%s scheduled_for=%s",
        contact_id,
        normalized_channel,
        _iso(scheduled_for),
    )


async def process_due_followups(settings: Settings) -> None:
    now = _utcnow()
    requeued = requeue_stale_sending_followups(settings.db_path, _iso(now - FOLLOWUP_SENDING_STALE_AFTER))
    if requeued:
        logger.warning("Follow-up requeued stale sending tasks count=%s", requeued)

    due_items = get_due_followups(settings.db_path, _iso(now))
    if not due_items:
        return

    manychat = ManyChatClient(settings)

    for item in due_items:
        contact_id = item["contact_id"]
        channel = (item["channel"] or "").strip().lower()
        scheduled_for = item["followup_scheduled_for"]
        last_user_message_at = item["last_user_message_at"]
        scheduled_from_message_at = item["scheduled_from_message_at"]

        if not claim_followup_for_sending(
            settings.db_path,
            contact_id=contact_id,
            expected_scheduled_for=scheduled_for,
            expected_last_user_message_at=last_user_message_at,
        ):
            continue

        if last_user_message_at != scheduled_from_message_at:
            update_followup_status(
                settings.db_path,
                contact_id=contact_id,
                status="skipped_user_replied",
                followup_scheduled_for=None,
                last_error=None,
            )
            logger.info(
                "Follow-up skipped because user replied contact_id=%s channel=%s",
                contact_id,
                channel,
            )
            continue

        last_user_dt = _parse_iso(last_user_message_at)
        if now - last_user_dt > FOLLOWUP_MAX_AGE:
            update_followup_status(
                settings.db_path,
                contact_id=contact_id,
                status="expired",
                followup_scheduled_for=None,
                last_error=None,
            )
            logger.info(
                "Follow-up skipped because expired contact_id=%s channel=%s last_user_message_at=%s",
                contact_id,
                channel,
                last_user_message_at,
            )
            continue

        flow_ns = manychat.resolve_followup_flow(channel)
        if not flow_ns:
            update_followup_status(
                settings.db_path,
                contact_id=contact_id,
                status="unsupported_channel",
                followup_scheduled_for=None,
                last_error="Follow-up flow is not configured for channel",
            )
            logger.warning(
                "Follow-up unsupported channel contact_id=%s channel=%s",
                contact_id,
                channel,
            )
            continue
        logger.info(
            "Follow-up flow selected contact_id=%s channel=%s flow_ns=%s",
            contact_id,
            channel,
            flow_ns,
        )

        try:
            followup_text = await _generate_followup_text(settings, contact_id, channel)
            logger.info("Follow-up generated contact_id=%s channel=%s", contact_id, channel)

            await manychat.save_followup_reply(contact_id, followup_text)
            add_message(settings.db_path, contact_id, "assistant", followup_text)
            await manychat.send_flow(contact_id, flow_ns)
            logger.info(
                "Follow-up flow sent contact_id=%s channel=%s flow_ns=%s",
                contact_id,
                channel,
                flow_ns,
            )
            update_followup_status(
                settings.db_path,
                contact_id=contact_id,
                status="sent",
                followup_sent_at=_iso(_utcnow()),
                followup_scheduled_for=None,
                last_error=None,
            )
            logger.info(
                "Follow-up sent contact_id=%s channel=%s flow_ns=%s",
                contact_id,
                channel,
                flow_ns,
            )
        except Exception as exc:
            retry_at = min(now + FOLLOWUP_RETRY_DELAY, last_user_dt + FOLLOWUP_MAX_AGE)
            if retry_at <= now:
                update_followup_status(
                    settings.db_path,
                    contact_id=contact_id,
                    status="expired",
                    followup_scheduled_for=None,
                    last_error=str(exc),
                )
                logger.exception(
                    "Follow-up send failed and expired contact_id=%s channel=%s",
                    contact_id,
                    channel,
                )
                continue

            update_followup_status(
                settings.db_path,
                contact_id=contact_id,
                status="scheduled",
                followup_scheduled_for=_iso(retry_at),
                retry_count_increment=True,
                last_error=str(exc),
            )
            logger.exception(
                "Follow-up send failed; rescheduled contact_id=%s channel=%s retry_at=%s",
                contact_id,
                channel,
                _iso(retry_at),
            )


async def run_followup_worker(settings: Settings) -> None:
    logger.info("Follow-up worker started poll_interval_seconds=%s", FOLLOWUP_POLL_INTERVAL_SECONDS)
    while True:
        try:
            await process_due_followups(settings)
        except Exception:
            logger.exception("Follow-up worker loop failed")
        await asyncio.sleep(FOLLOWUP_POLL_INTERVAL_SECONDS)
