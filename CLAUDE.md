# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pinta is a FastAPI backend + React frontend + Telegram bot for "Maler
Kostenvoranschlag" — an AI-powered quote generator for painting contractors
in DE/AT. Quote generation runs through a **pytaskforce-based agent**
("Manfred"), which both the Web App and the Telegram bot reach via the
unified `/api/v1/agent/*` HTTP endpoint. PostgreSQL/SQLite for data, Redis
optional for caching.

**Note**: README.md still mentions Flask in places; the codebase actually
uses **FastAPI** — that's the authoritative framework.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│ React Web App   │    │ Telegram Bot    │
│ (frontend/)     │    │ (run as adapter)│
└───────┬─────────┘    └────────┬────────┘
        │ HTTP/JWT             │ HTTP/Bot-Service-Token
        ▼                      ▼
┌──────────────────────────────────────────┐
│   FastAPI Backend (backend/src/main.py)  │
│   ─ /api/v1/auth /users /quotes /...     │
│   ─ /api/v1/ai/quick-quote (agent-backed)│
│   ─ /api/v1/agent/chat[/stream]          │   ← unified agent endpoint
│   ─ /api/v1/agent/bot/{chat,reset,link}  │   ← bot-service-token auth
│   ─ AgentService → pytaskforce LeanAgent │
│       Tools: python, search_materials,   │
│              save_quote_to_db,           │
│              generate_quote_pdf,         │
│              multimedia                  │
└────────────────┬─────────────────────────┘
                 ▼
         ┌──────────────────┐
         │  Pinta DB         │  ← single source of truth
         │  User, Quote,     │
         │  QuoteItem,       │
         │  Document,        │
         │  Conversation,    │   stage 1
         │  ConversationMsg, │   stage 1
         │  ChannelLink,     │   stage 1 (telegram chat ↔ user)
         │  MaterialPrice    │
         └──────────────────┘
```

## Key Components

### FastAPI Backend (`backend/src/`)
- **main.py** — app factory, lifespan starts AgentFactory, security tasks,
  quota scheduler, Redis cache.
- **routes/** — auth, users, quotes, ai, payments, chat, documents, quota,
  materials, **agent** (unified endpoint).
- **services/** — `agent_service.py` (façade around pytaskforce LeanAgent +
  DB-backed conversation memory), `channel_link_service.py` (telegram chat
  ↔ user mapping with shadow-user creation + linking-token flow),
  `ai_service.py` (legacy single-shot prompts; still used by older routes
  like analyze-project), `quote_calculator.py` (deterministic math),
  `rag_service.py` (cosine search over MaterialPrice), `pdf_service.py` /
  `professional_pdf_service.py` (legacy PDF code, mostly unused now).
- **agents/** — pytaskforce wiring: `factory.py` (warm AgentFactory,
  register tools), `taskforce_setup.py` (env bridge AZURE_OPENAI_* →
  AZURE_API_*), `tools/` (Pinta-specific ToolProtocol implementations).

### Pinta Agent Tools (`backend/src/agents/tools/`)
Registered via `register_pinta_tools()` in `agents/factory.py`:
- **search_materials** — RAG over `material_prices` table; gracefully
  empty when table is missing.
- **save_quote_to_db** — inserts a `Quote` + `QuoteItem` rows for the
  active user (read from `current_user_id` ContextVar). Must run BEFORE
  `generate_quote_pdf` so the PDF can attach to the freshly created Quote.
- **generate_quote_pdf** — renders the quote dict via reportlab and
  ALSO inserts a `Document` row pointing at the file. PDFs land in
  `backend/.taskforce_maler/quotes/`.

Plus pytaskforce native tools used by the agent: `python` (sandboxed
arithmetic), `multimedia` (image vision + PDF text extraction).

### Telegram bot (`backend/src/telegram/runner.py` + `scripts/run_telegram_bot.py`)
- Long-polling adapter via pytaskforce's `TelegramPoller` /
  `TelegramOutboundSender`.
- Owns NO agent logic — every inbound message is forwarded to
  `POST /api/v1/agent/bot/chat` with `X-Bot-Service-Token`,
  `X-Channel: telegram`, `X-External-Id: <chat_id>` headers.
- PDF send: backend returns a `pdf_filename`, bot uploads
  `backend/.taskforce_maler/quotes/<filename>` via `sendDocument`.
  Works only because bot + backend share the local FS in dev — split
  deployment would route through `/api/v1/agent/pdf/<name>` instead.
- Commands: `/neu`, `/new`, `/reset` (archive active conversation),
  `/start [token]`, `/link <token>` (consume a Web-issued linking token).

### Database Models (`backend/src/models/models.py`)
- **User** — auth, premium, quota counters, `hourly_rate`,
  `material_cost_markup`. `is_active=True, is_verified=False` for
  bot-created shadow users.
- **Quote / QuoteItem** — single source of truth for quotes from any
  channel.
- **Document** — file uploads + agent-generated PDFs.
- **Conversation / ConversationMessage** — per-user, channel-tagged
  agent thread; `is_active=True` for the current thread, archived on
  `/neu`. Backs the agent's chat memory.
- **ChannelLink** — `(channel, external_id) → user_id` mapping.
  `is_anonymous_shadow=True` for auto-created users from Telegram.
  `linking_token` is a one-shot 24h secret issued by the Web for
  `/start <token>` / `/link <token>` hand-off.
- **MaterialPrice** — RAG knowledge base; embeddings as JSON text so the
  table works on SQLite without pgvector.

## Import Path

The code uses `src/` as the Python package root inside `backend/`. From
the project root:
```python
from src.core.database import Base
from src.models.models import User
from src.routes.auth import router
```
PYTHONPATH must include `backend/`. Tests/scripts handle this via
`sys.path.insert(0, str(REPO_ROOT / "backend"))`.

Local imports in functions are used to break circular dependencies (e.g.
`get_current_user` imports `User` lazily inside the function body).

## Environment Setup

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e ..\..\pytaskforce   # editable install of the agent framework

# Frontend
cd ..\frontend
npm install
```

### Required `.env` keys (file lives at the **repo root**, not `backend/`)
```
# Auth
SECRET_KEY=<32+ chars>

# OpenAI / Azure (backend AND bot read this)
OPENAI_API_KEY=sk-...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-10-21
AGENT_LLM_MODEL_ALIAS=main          # main | fast | claude-sonnet | ...

# Telegram
TELEGRAM_BOT_TOKEN=<BotFather token>
BOT_SERVICE_TOKEN=<long random secret — bot ↔ backend HMAC equivalent>
BOT_BACKEND_URL=http://127.0.0.1:8000

# Stripe (optional in dev, enforced in prod)
STRIPE_SECRET_KEY=...
STRIPE_PRICE_ID=...
STRIPE_WEBHOOK_SECRET=...
```

`AZURE_OPENAI_*` is auto-bridged to LiteLLM's `AZURE_API_*` convention by
`backend/src/agents/taskforce_setup.py::ensure_litellm_env_for_taskforce`.

## Running

```powershell
# Backend (from project root)
cd backend
.\.venv\Scripts\python.exe -m uvicorn src.main:app --port 8000 --reload

# Telegram bot (from project root)
backend\.venv\Scripts\python.exe scripts\run_telegram_bot.py

# Frontend dev server
cd frontend
npm run dev
```

The bot expects the backend to be reachable at `BOT_BACKEND_URL`; both
processes can run on the same host.

## Database Management

### Alembic
```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "msg"
```

`alembic/env.py` strips the async driver from `DATABASE_URL`
(`sqlite+aiosqlite` → `sqlite`, `postgresql+asyncpg` →
`postgresql+psycopg2`) so the sync Engine inside Alembic works.

### Existing-DB caveat
`init_db()` (Base.metadata.create_all on app startup) creates tables from
the models without touching `alembic_version`. If you start the app first
and only later run alembic, tables exist but the version table is empty
and `alembic upgrade head` re-runs migrations from 001 → 500-error. Fix:
`alembic stamp <last-revision-applied>` first, then `upgrade head`.

### Migrations
- 001 — initial PostgreSQL schema
- 002 — enhanced document processing (revision id is `002_enhanced_docs`,
  NOT `002_enhanced_document_processing`; 003 used to reference the wrong
  name and was fixed in stage 1)
- 003 — quota management
- 004 — user cost parameters
- 005 — material_prices (RAG)
- 006 — unified agent schema (Conversation, ConversationMessage,
  ChannelLink)

## Testing

```powershell
# All tests
python scripts/run_tests.py all

# Specific suites
python scripts/run_tests.py auth | quotes | ai | documents | users

# With coverage / parallel
python scripts/run_tests.py coverage
python scripts/run_tests.py all --parallel

# Or via make
make test
```

Tests use in-memory SQLite, mock `AIService` calls, and create an
isolated FastAPI app to avoid main-app side effects. `conftest.py`
provides fixtures `test_user`, `auth_headers`, `test_quote`.

The agent path itself isn't yet covered by integration tests (would
require an OpenAI mock at the LiteLLM layer); regression tests for the
prompt builder and quote calculator live in
`backend/tests/test_ai_prompts_smoke.py` and
`backend/tests/test_quote_calculator.py`.

## API Surface (key endpoints)

### Unified agent (use this for all new development)
- `POST /api/v1/agent/chat` — sync chat, JWT-auth, returns
  `{conversation_id, final_message, humanized_message, pdf_url, …}`.
- `POST /api/v1/agent/chat/stream` — SSE stream, same auth.
- `GET  /api/v1/agent/conversations` — user's conversations list.
- `GET  /api/v1/agent/conversations/{id}/messages` — full transcript.
- `POST /api/v1/agent/reset` — archive active, start fresh.
- `GET  /api/v1/agent/pdf/{name}` — auth-gated PDF download.
- `POST /api/v1/agent/linking-token` — Web user issues a token to paste
  into Telegram.
- `POST /api/v1/agent/bot/chat` — bot-service-token auth, headers
  `X-Bot-Service-Token`, `X-Channel`, `X-External-Id`. Auto-creates
  shadow user on first contact.
- `POST /api/v1/agent/bot/reset` — same auth, archive active.
- `POST /api/v1/agent/bot/link` — consume a linking token issued via
  `/agent/linking-token` (rebinds shadow link to the real user).

### Legacy (kept for backwards compatibility)
- `POST /api/v1/ai/quick-quote` — STILL EXISTS but now delegates
  internally to the unified agent (stage 4). Same request/response
  schema as before so the React frontend keeps working unchanged.
- `POST /api/v1/ai/analyze-project` and `POST /api/v1/ai/generate-quote`
  — still on the legacy single-shot `AIService` path. Will be migrated
  when the frontend switches to the unified `/agent/chat`.

### Other (unchanged)
- `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/quotes/*`,
  `/api/v1/documents/*`, `/api/v1/payments/*`, `/api/v1/quota/*`,
  `/api/v1/materials/*`, `/api/v1/chat/*`.

## pytaskforce integration notes

- pytaskforce is installed editable from a sibling repo
  (`C:\Users\rudi\source\pytaskforce`) via `pip install -e`.
- `AgentFactory` is warmed once at FastAPI startup
  (`agent_service.start()` in lifespan); per-mission a fresh `LeanAgent`
  is created (LeanAgent's message buffer is NOT parallel-safe across
  missions, so reuse across chats would clobber).
- Tools are registered in pytaskforce's global `_TOOL_REGISTRY` via
  `register_tool(name, type, module)` from
  `taskforce.infrastructure.tools.registry`.
- The agent reads `AGENT_LLM_MODEL_ALIAS` from settings (default `main`
  → `azure/gpt-5.4-mini` per pytaskforce's `configs/llm_config.yaml`).
  Switch model without code change.
- Agent state lives in `backend/.taskforce_maler/` (gitignored). Quote
  PDFs land in `backend/.taskforce_maler/quotes/`. Conversation history
  lives in the Pinta DB, NOT in pytaskforce's StateManager — we splice
  it into the mission as a "Bisheriger Chat-Verlauf" prefix because
  `LeanAgent.execute_stream` doesn't accept a prior-messages parameter.

## Common Gotchas

- **`OPENAI_API_KEY` env var beats `.env`** — pydantic-settings prefers
  process env over file. The Telegram-bot smoke script (`scripts/`)
  pops the env var on startup so the .env value wins.
- **`material_prices` table missing** — common when DB was created via
  `init_db()` before stage 1 migrations ran. `search_materials` already
  handles this (returns empty list with a "do not retry" hint), so the
  agent falls back to faustregeln from the system prompt.
- **`maler.yaml` is loaded by Pinta**, not by pytaskforce. The file
  lives at `backend/agents/maler.yaml` and we read it ourselves with
  PyYAML; only `system_prompt` and `tools` are passed inline to
  `factory.create_agent`.
- **PDF document_id in tool result** — `generate_quote_pdf` now also
  inserts a `Document` row. If you need to find a generated PDF later
  via the documents API, query for `mime_type='application/pdf'` +
  user_id.
- **Shadow users** are auto-created on first Telegram contact with
  `email=tg-<chat_id>-<random>@telegram.shadow`. They have a random
  password they can never use. They DON'T count against quota the same
  way regular users do — be aware when monitoring.

## Memory & Auto-Loaded Context

The `~/.claude/projects/.../memory/` directory holds user/project memory.
Don't duplicate that information here — CLAUDE.md is for code/repo facts
only, memory is for evolving context.

## Performance / Cost Notes

- Quote generation via the agent: ~10k tokens, 20-40s end-to-end against
  `azure/gpt-5.4-mini`. Burst-tolerant per user, but costly to chain.
- Agent state caching is per-conversation (`session_id=pinta-conv-<id>`)
  so follow-up turns reuse the planner's state.
- Telegram is NOT throttled in our code; pytaskforce's
  `TelegramOutboundSender` retries 429s. For prod load, add an inbound
  rate limiter in front of `/api/v1/agent/bot/chat`.
