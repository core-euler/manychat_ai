from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = Field(default=3000, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    db_path: str = Field(default="./db/conversations.sqlite", alias="DB_PATH")

    comet_api_url: str = Field(default="https://api.cometapi.com", alias="COMET_API_URL")
    comet_api_key: str = Field(alias="COMET_API_KEY")
    comet_model: str = Field(default="gpt-5-chat-latest", alias="COMET_MODEL")
    comet_max_tokens: int = Field(default=500, alias="COMET_MAX_TOKENS")

    manychat_api_url: str = Field(default="https://api.manychat.com", alias="MANYCHAT_API_URL")
    manychat_api_token: str = Field(alias="MANYCHAT_API_TOKEN")
    manychat_reply_flow_instagram: str | None = Field(default=None, alias="MANYCHAT_REPLY_FLOW_INSTAGRAM")
    manychat_reply_flow_facebook: str | None = Field(default=None, alias="MANYCHAT_REPLY_FLOW_FACEBOOK")
    manychat_followup_flow_instagram: str | None = Field(default=None, alias="MANYCHAT_FOLLOWUP_FLOW_INSTAGRAM")
    manychat_followup_flow_facebook: str | None = Field(default=None, alias="MANYCHAT_FOLLOWUP_FLOW_FACEBOOK")
    # Backward-compatible fallback when channel-specific flow is not configured.
    manychat_send_flow_ns: str | None = Field(default=None, alias="MANYCHAT_SEND_FLOW_NS")
    manychat_field_ai_reply: str = Field(default="ai_reply", alias="MANYCHAT_FIELD_AI_REPLY")
    manychat_field_ai_followup: str = Field(default="ai_followup_reply", alias="MANYCHAT_FIELD_AI_FOLLOWUP")
    manychat_field_handoff: str = Field(default="handoff_flag", alias="MANYCHAT_FIELD_HANDOFF")

    manychat_webhook_secret: str | None = Field(default=None, alias="MANYCHAT_WEBHOOK_SECRET")
    internal_api_secret: str | None = Field(default=None, alias="INTERNAL_API_SECRET")

    system_prompt_path: str = Field(default="system_prompt.txt", alias="SYSTEM_PROMPT_PATH")
    followup_prompt_path: str = Field(default="followup_prompt.txt", alias="FOLLOWUP_PROMPT_PATH")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
