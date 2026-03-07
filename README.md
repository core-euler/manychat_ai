# Tattoo 44 AI Backend (FastAPI)

Backend for ManyChat async AI replies using CometAPI.

## What is implemented

- `POST /webhook/manychat`:
  - validates payload from ManyChat
  - returns `{"status":"ok"}` immediately
  - processes message in background
- `POST /manychat-callback` (internal utility endpoint):
  - writes `ai_reply` and `handoff_flag` to ManyChat
  - triggers `Send AI Reply` flow
- `GET /health`
- SQLite conversation history (`contact_id`, `role`, `content`, `created_at`)
- Handoff detection via `[HANDOFF]`
- Channel limits:
  - Instagram: 1000 chars
  - Facebook/WhatsApp: 2000 chars

## Configuration

1. Copy `.env.example` to `.env`
2. Set values:
   - `COMET_API_KEY`
   - `COMET_MODEL`
   - `MANYCHAT_API_TOKEN`
   - `MANYCHAT_REPLY_FLOW_INSTAGRAM`
   - `MANYCHAT_REPLY_FLOW_FACEBOOK`
   - `MANYCHAT_FOLLOWUP_FLOW_INSTAGRAM`
   - `MANYCHAT_FOLLOWUP_FLOW_FACEBOOK`
   - `MANYCHAT_FIELD_AI_FOLLOWUP` (default: `ai_followup_reply`)
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_ID` (optional admin notifications)
   - optionally `INTERNAL_API_SECRET` to protect `/manychat-callback`
3. Put your production prompt into `system_prompt.txt`
4. Put your follow-up prompt into `followup_prompt.txt`

## Run with Docker Compose

```bash
docker compose up --build
```

Backend will be available at:

- `http://localhost:3000/health`

## API references

- CometAPI chat completions: `docs/API.md`
- Project requirements/spec: `docs/SPEC.md`
