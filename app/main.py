from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from app.clients.manychat import ManyChatClient
from app.config import get_settings
from app.db import init_db
from app.schemas import (
    HealthResponse,
    ManyChatCallbackIn,
    ManyChatWebhookIn,
    WebhookAckResponse,
)
from app.services.chat_processor import process_incoming_message

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Tattoo44 AI Backend", version="1.0.0")


@app.on_event("startup")
def startup_event() -> None:
    init_db(settings.db_path)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/webhook/manychat", response_model=WebhookAckResponse)
async def manychat_webhook(
    payload: ManyChatWebhookIn,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> WebhookAckResponse:
    if settings.manychat_webhook_secret:
        if x_webhook_secret != settings.manychat_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    background_tasks.add_task(process_incoming_message, payload, settings)
    return WebhookAckResponse(status="ok")


@app.post("/manychat-callback", response_model=WebhookAckResponse)
async def manychat_callback(
    payload: ManyChatCallbackIn,
    x_internal_secret: str | None = Header(default=None),
) -> WebhookAckResponse:
    if settings.internal_api_secret:
        if x_internal_secret != settings.internal_api_secret:
            raise HTTPException(status_code=401, detail="Invalid internal secret")

    client = ManyChatClient(settings)
    await client.save_reply_and_handoff(payload.contact_id, payload.reply_text, payload.handoff)
    if not settings.manychat_send_flow_ns:
        raise HTTPException(status_code=400, detail="MANYCHAT_SEND_FLOW_NS is required for /manychat-callback")
    await client.send_flow(payload.contact_id, settings.manychat_send_flow_ns)
    return WebhookAckResponse(status="ok")
