from typing import Literal

from pydantic import BaseModel, Field


class ManyChatWebhookIn(BaseModel):
    contact_id: str = Field(min_length=1)
    channel: Literal["instagram", "facebook", "whatsapp"]
    first_name: str | None = None
    last_name: str | None = None
    last_input: str = Field(min_length=1)


class HealthResponse(BaseModel):
    status: str = "ok"


class WebhookAckResponse(BaseModel):
    status: str = "ok"


class ManyChatCallbackIn(BaseModel):
    contact_id: str = Field(min_length=1)
    reply_text: str = Field(min_length=1)
    handoff: bool = False
