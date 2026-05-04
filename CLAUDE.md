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
  materials, **agent** (unified endpoint), **onboarding** (mandatory
  3-step wizard for new users).
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
  `material_cost_markup`, `vat_id`, `logo_path`,
  `onboarding_completed_at` (added in migration 007 — the dashboard is
  gated until `onboarding_completed_at IS NOT NULL`).
  `is_active=True, is_verified=False` for bot-created shadow users.
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

# LLM provider — pick at least one. Pinta auto-detects which to use:
# Azure has priority if both are set. Override with LLM_PROVIDER=azure|openai.

# Plain OpenAI:
OPENAI_API_KEY=sk-...

# Azure OpenAI:
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-10-21

# Optional: pin a specific model alias (overrides provider default).
# Aliases are defined in backend/agents/llm_config.yaml:
#   main / fast / powerful / legacy        → azure/gpt-5.4-* / azure/gpt-4.1
#   openai-main / openai-fast / openai-powerful → openai/gpt-4o-mini / gpt-4o
AGENT_LLM_MODEL_ALIAS=main

# Telegram
TELEGRAM_BOT_TOKEN=<BotFather token>
BOT_SERVICE_TOKEN=<long random secret — bot ↔ backend HMAC equivalent>
BOT_BACKEND_URL=http://127.0.0.1:8000

# Stripe (optional in dev, enforced in prod)
STRIPE_SECRET_KEY=...
STRIPE_PRICE_ID=...
STRIPE_WEBHOOK_SECRET=...
```

`AZURE_OPENAI_*` is auto-bridged to LiteLLM's `AZURE_API_*` convention
by `backend/src/agents/taskforce_setup.py::ensure_litellm_env_for_taskforce`.
The same function detects whether to validate Azure or plain-OpenAI
credentials based on `settings.llm_provider` (auto-derived from .env).
At startup, `factory.warm_factory()` renders a provider-aware copy of
`maler.yaml` into `.taskforce_maler/profiles/maler.yaml` with an
`llm:` block pointing at `backend/agents/llm_config.yaml` and the
right `default_model` (`main` for Azure, `openai-main` for plain
OpenAI). The `.env` is read from BOTH `backend/.env` and the repo-root
`.env`; root values override backend, so the canonical place to put
secrets is the root file (per CLAUDE.md convention).

## Running

```powershell
# All three at once (opens three pwsh windows: backend, bot, frontend)
.\scripts\start_dev.ps1
.\scripts\start_dev.ps1 -BackendPort 8001    # if 8000 is phantom-occupied

# Stop
.\scripts\stop_dev.ps1                       # just the launched windows
.\scripts\stop_dev.ps1 -All                  # + any listener on 8000/8001/5173/5183

# Or run individually:
cd backend
.\.venv\Scripts\python.exe -m uvicorn src.main:app --port 8000 --reload

backend\.venv\Scripts\python.exe scripts\run_telegram_bot.py

cd frontend
npm run dev
```

The bot expects the backend to be reachable at `BOT_BACKEND_URL`. The
launcher sets this automatically based on `-BackendPort`. When running
the bot manually, set it via env (`$env:BOT_BACKEND_URL = "http://127.0.0.1:8001"`)
if you're not on the default 8000.

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
- 007 — user onboarding fields (`vat_id`, `logo_path`,
  `onboarding_completed_at`)

## Testing

```powershell
# Deterministic MVP gate (matches CI; 46+ green tests)
$env:PYTHONPATH = "C:\Users\rudi\source\pinta\backend"
cd backend
.\.venv\Scripts\python.exe -m pytest `
  tests/test_quote_pdf_routes.py `
  tests/test_onboarding.py `
  tests/test_agent_service.py `
  tests/test_quote_search.py `
  tests/test_ai_prompts_smoke.py `
  tests/test_quote_calculator.py

# Full suite (includes pre-MVP class-based suites — many of those
# still red, see conftest.py header for context)
python scripts/run_tests.py all
```

Tests use in-memory SQLite and create an isolated FastAPI app via
`conftest.py::create_test_app()` so the main app's lifespan doesn't
fire. Fixtures: `test_user`, `auth_headers`, `test_quote`,
`test_session`, `client`.

**Test pyramid as of 0.1:**
- Unit (no LLM, no DB-app): `test_agent_service.py` covers
  `build_mission_with_history` (incl. `prior_quotes` splice),
  `extract_pdf_path_from_event`, `extract_quote_ref_from_event`,
  `recent_quotes` against the test session.
- Integration (FastAPI TestClient + in-memory SQLite):
  `test_onboarding.py`, `test_quote_pdf_routes.py`,
  `test_quote_search.py`, `test_ai_prompts_smoke.py`. **No live LLM
  calls** — the agent path isn't yet exercised end-to-end here; the
  pattern (recommended in the plan) is to monkey-patch
  `agent_service.chat` at the AgentService layer rather than mocking
  LiteLLM internals.
- E2E (Playwright, Chromium, mock-only): `frontend/tests/e2e/*.spec.js`
  with route-mocking helpers in `helpers/apiMocks.js`. CI runs them
  against `npm run dev` (vite picks up our env at port 5183).

The legacy class-based suites (`TestUsersIntegration`,
`TestQuotesIntegration`, `TestAuthIntegration`,
`TestAIIntegration`, `TestDocumentsIntegration`) reference endpoints
that were never implemented (e.g. `/users/statistics`,
`/users/settings`, OAuth2-form login). They are quarantined out of
the CI gate; cleanup is per-endpoint and tracked separately.

## API Surface (key endpoints)

### Unified agent (use this for all new development)
- `POST /api/v1/agent/chat` — sync chat, JWT-auth, returns
  `{conversation_id, final_message, humanized_message, pdf_url, …}`.
- `POST /api/v1/agent/chat/stream` — SSE stream, same auth.
- `GET  /api/v1/agent/conversations` — user's conversations list.
- `GET  /api/v1/agent/conversations/{id}/messages` — full transcript.
- `POST /api/v1/agent/reset` — archive active, start fresh.
- `GET  /api/v1/agent/pdf/{name}` — auth-gated PDF download
  (path-traversal protected).
- `POST /api/v1/agent/linking-token` — Web user issues a token to paste
  into Telegram.
- `POST /api/v1/agent/bot/chat` — bot-service-token auth, headers
  `X-Bot-Service-Token`, `X-Channel`, `X-External-Id`. Auto-creates
  shadow user on first contact.
- `POST /api/v1/agent/bot/reset` — same auth, archive active.
- `POST /api/v1/agent/bot/link` — consume a linking token issued via
  `/agent/linking-token` (rebinds shadow link to the real user).

### Onboarding
- `GET  /api/v1/onboarding/status` — `{completed, missing[], user}`.
- `POST /api/v1/onboarding/complete` — body
  `{company_name, address, vat_id?, hourly_rate, material_cost_markup}`,
  idempotent.
- `POST /api/v1/onboarding/logo` — multipart, ≤ 1 MB, mime ∈
  `{png, jpeg, webp, svg+xml}`; logo path stored relative to the
  uploads root.

### Quotes (MVP entry points)
- `GET  /api/v1/quotes/?q=…` — substring search across customer name,
  project title, quote number (case-insensitive). Powers the
  dashboard search field.
- `GET  /api/v1/quotes/{id}/agent-pdf-info` — bridge from a Quote
  record to its agent-generated PDF in `.taskforce_maler/quotes/`.
  Returns `{pdf_filename, pdf_url}` so the frontend can call
  `GET /api/v1/agent/pdf/{name}`.

### Legacy (kept for backwards compatibility, deprecated in 0.1)
- `POST /api/v1/ai/quick-quote` — STILL EXISTS but delegates
  internally to the unified agent. Same request/response schema as
  before so the React frontend keeps working unchanged.
- `POST /api/v1/ai/analyze-project` and `POST /api/v1/ai/generate-quote`
  — still on the legacy single-shot `AIService` path.
- `POST /api/v1/quotes/{id}/pdf/generate` and
  `GET /api/v1/quotes/{id}/pdf/download` — marked `deprecated=True`,
  agent-generated quotes won't be found there. Use the
  `agent-pdf-info` route instead. Slated for removal in 0.2.

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
- **Quote-memory splice** (since 0.1) — `agent_service.recent_quotes()`
  loads the user's last 5 quotes and `build_mission_with_history`
  injects them as a "Letzte Angebote dieses Nutzers" block ahead of
  the chat history. Cap is `_QUOTE_MEMORY_LIMIT` in `agent_service.py`.

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
- **Onboarding gate is bypassed for the demo user** —
  `useAuth.onboardingComplete` is forced `true` when
  `demoMode === true` (detected by `userData.email === 'demo@example.com'`).
  Real users land on `/onboarding` until `onboarding_completed_at` is
  set; the gate lives in `frontend/src/components/PrivateRoute.jsx`.
- **Frontend dev port** — Vite is `strictPort: 5183`. The unusual port
  avoids a collision with the sibling pytaskforce admin UI on
  `localhost:5173`. If another tool tries to grab 5183, vite fails
  fast rather than silently moving to a different port.

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
