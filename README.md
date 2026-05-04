# Pinta — KI-gestützter Kostenvoranschlags-Generator für Maler

Pinta ist ein Werkzeug für Malerbetriebe, das Kostenvoranschläge per Chat
oder Web-Formular erzeugt. Im Hintergrund läuft **Manfred** — ein
pytaskforce-basierter KI-Agent, der Domänen-Wissen für Malerarbeiten in
DE/AT mitbringt, mit Tools rechnet (deterministische Mathematik statt
LLM-Halluzinationen), Fotos und Pläne lesen kann und am Ende ein
professionelles A4-PDF erzeugt.

## Wege, mit Pinta zu arbeiten

| Kanal | Login | Was geht |
|-------|-------|----------|
| **Web App** (React) | Pinta-Account | Voll: Quotes, Dashboard, PDFs, Stripe, Telegram-Token erzeugen |
| **Telegram Bot** | optional verknüpft | Chat mit Manfred, Foto/PDF-Upload, PDF-Download |
| **REST-API** | JWT | Direktintegration in eigene Tools |

Beide Frontends sprechen dieselbe API (`/api/v1/agent/*`), schreiben in
dieselbe DB und nutzen denselben Agent.

## Features

- **Manfred, der KI-Maler-Agent** — Prompt + Tool-Use über pytaskforce,
  Modell konfigurierbar (Default `azure/gpt-5.4-mini`).
- **Multimodal** — Fotos vom Raum oder mitgeschickte Pläne werden vom
  `multimedia`-Tool gelesen, der Agent leitet daraus Mengen und
  Vorarbeiten ab.
- **Deterministische Mathematik** — `python`-Tool macht Flächen-,
  Mengen-, Lohn- und MwSt-Berechnungen, kein LLM-Drift bei den Zahlen.
- **A4-PDF-Generator** — `generate_quote_pdf` (reportlab platypus) liefert
  einen Voranschlag, der direkt an den Endkunden weitergeschickt werden
  kann. PDF wird als `Document`-Datensatz in der DB gespeichert.
- **Persistente Chat-Memory** — pro User + Kanal, geteilt zwischen
  Telegram und Web (Tabellen `conversations`, `conversation_messages`).
- **Telegram ↔ Web verlinken** — kurzlebiger Token aus dem Dashboard,
  paste in den Bot via `/link <token>`, Bot- und Web-Sicht teilen ab dann
  alle Quotes, Dokumente und Conversation-Threads.
- **Freemium-Quota** — 3 kostenlose Quotes pro Monat, Premium / Pakete
  via Stripe.

## Tech-Stack

### Frontend
- **React 18** + TypeScript
- **TailwindCSS** + **shadcn/ui**
- **Vite** als Build-Tool

### Backend
- **FastAPI** (Python 3.11+)
- **SQLAlchemy 2.x async** (SQLite dev, PostgreSQL prod)
- **Alembic** Migrations
- **pytaskforce** als Agent-Framework (sibling-Repo,
  `pip install -e ../pytaskforce`)
- **LiteLLM** + **Azure OpenAI** (default) — auch OpenAI/Anthropic/Ollama
  per `AGENT_LLM_MODEL_ALIAS`
- **reportlab** für PDFs · **pdfplumber/PyPDF2** über `multimedia`-Tool
  für PDF-Text · **Tesseract** für OCR-Pfade
- **Stripe** für Payments
- **Redis** optional für Caching

### Telegram
- pytaskforce-eigener `TelegramPoller` (Long-Polling, kein Webhook nötig)
- `BackendClient` im Bot-Adapter ruft `/api/v1/agent/bot/*` über HTTP

## Voraussetzungen

- **Python 3.11+**
- **Node.js 18+**
- **Git**
- **pytaskforce-Repo** als Sibling-Verzeichnis
  (`../pytaskforce` relativ zum Pinta-Repo)
- Optional: Tesseract OCR + poppler-utils für Document-Pipeline

## Installation

### 1. Repo klonen
```powershell
git clone <repository-url>
cd pinta
```

### 2. Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
pip install -r requirements.txt
pip install -e ..\..\pytaskforce  # editable install des Agent-Frameworks
```

### 3. Frontend
```powershell
cd ..\frontend
npm install
```

### 4. `.env` (im **Repo-Root**, nicht in `backend/`)
```ini
# Auth
SECRET_KEY=<min. 32 Zeichen>

# OpenAI / Azure (eines reicht — Default ist Azure)
OPENAI_API_KEY=sk-...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-10-21
AGENT_LLM_MODEL_ALIAS=main          # main|fast|claude-sonnet|...

# Telegram (nur wenn Bot genutzt wird)
TELEGRAM_BOT_TOKEN=<BotFather-Token>
BOT_SERVICE_TOKEN=<langer Random-Secret-String>
BOT_BACKEND_URL=http://127.0.0.1:8000

# Stripe (in dev optional)
STRIPE_SECRET_KEY=...
STRIPE_PRICE_ID=...
STRIPE_WEBHOOK_SECRET=...

# E-Mail (optional)
SMTP_HOST=...
SMTP_USER=...
SMTP_PASSWORD=...
```

`BOT_SERVICE_TOKEN` generierst du z. B. mit:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Datenbank initialisieren
```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 6. (Optional) System-Tools
```bash
# Linux/macOS
sudo apt install tesseract-ocr tesseract-ocr-deu poppler-utils
# Windows
choco install tesseract poppler
```

## Starten

### Backend
```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn src.main:app --port 8000 --reload
```
→ http://localhost:8000  ·  Health: http://localhost:8000/health

### Frontend
```powershell
cd frontend
npm run dev
```
→ http://localhost:5183

### Telegram-Bot
```powershell
backend\.venv\Scripts\python.exe scripts\run_telegram_bot.py
```
Long-Polling, kein Webhook nötig. Bricht beim Start ab, falls
`TELEGRAM_BOT_TOKEN` oder `BOT_SERVICE_TOKEN` fehlen — mit klarer
Anweisung was zu setzen ist.

## Projektstruktur

```
pinta/
├── backend/
│   ├── src/
│   │   ├── agents/             # pytaskforce-Wiring
│   │   │   ├── factory.py      # warm AgentFactory, register Pinta-Tools
│   │   │   ├── taskforce_setup.py
│   │   │   └── tools/          # search_materials, save_quote_to_db,
│   │   │                       #   generate_quote_pdf
│   │   ├── core/               # database, security, settings, cache
│   │   ├── models/models.py    # User, Quote, QuoteItem, Document,
│   │   │                       #   Conversation, ConversationMessage,
│   │   │                       #   ChannelLink, MaterialPrice, …
│   │   ├── routes/             # auth, users, quotes, ai, payments,
│   │   │                       #   chat, documents, quota, materials,
│   │   │                       #   agent  ← unified endpoint
│   │   ├── services/           # agent_service, channel_link_service,
│   │   │                       #   ai_service (legacy), quote_calculator,
│   │   │                       #   rag_service, pdf_service, …
│   │   ├── telegram/runner.py  # Bot-Adapter (HTTP gegen agent endpoint)
│   │   └── main.py             # FastAPI app
│   ├── agents/maler.yaml       # System-Prompt + Tool-Liste für Manfred
│   ├── alembic/                # DB-Migrationen
│   ├── tests/
│   └── requirements.txt
├── frontend/                   # React-App (Vite + TS)
├── scripts/
│   ├── run_telegram_bot.py     # Standalone Bot-Runner
│   ├── iter1_baseline.py … iter4_agent.py   # Eval-Skripte
│   └── smoke_*.py              # diverse Smoke-Tests
├── iteration_logs/             # JSON-Outputs + Auswertungen
│                               #   der Quote-Generierung
├── CLAUDE.md                   # Projekt-Doku für KI-Coding-Assistenten
├── DOCUMENTATION.md
├── API_DOCUMENTATION.md
├── BENUTZERHANDBUCH.md
└── README.md
```

## Architektur (Kurzfassung)

```
React Web App ──┐                     ┌── Telegram-Bot (Long-Polling)
                │                     │
                ▼ HTTP/JWT            ▼ HTTP/Bot-Service-Token
   ┌──────────────────────────────────────────┐
   │          FastAPI Backend                  │
   │  /api/v1/agent/chat[/stream]              │
   │  /api/v1/agent/bot/{chat,reset,link}      │
   │  /api/v1/auth /quotes /documents /…       │
   │            ↓                              │
   │  AgentService → pytaskforce LeanAgent     │
   │  Tools: python, multimedia,               │
   │         search_materials,                 │
   │         save_quote_to_db,                 │
   │         generate_quote_pdf                │
   └────────────┬──────────────────────────────┘
                ▼
        ┌─────────────────────┐
        │  Pinta DB (Single-  │
        │  Source-of-Truth)   │
        └─────────────────────┘
```

Details: siehe [`CLAUDE.md`](CLAUDE.md).

## Telegram-Verknüpfung Web ↔ Bot

1. Im Web-Dashboard: `POST /api/v1/agent/linking-token` → Token (24 h gültig).
2. Im Telegram an Manfred schreiben: `/link <token>`.
3. Ab dann: alle bisherigen anonymen Schatten-Conversations dieses
   Telegram-Chats wandern auf den Pinta-Account, neue Quotes erscheinen
   sofort im Dashboard.

## Tests

```powershell
# Alle Suites
python scripts/run_tests.py all

# Einzelne
python scripts/run_tests.py auth | quotes | ai | documents | users

# Coverage
python scripts/run_tests.py coverage
make test
```

Tests nutzen In-Memory-SQLite und mocken AI-Calls. Smoke-Tests für den
Quote-Calculator und den Prompt-Builder unter `backend/tests/`.

## Entwickler-Workflow

- Neue Domain-Logik bevorzugt als pytaskforce-Tool
  (`backend/src/agents/tools/<name>.py` + Eintrag in
  `factory.register_pinta_tools`). Siehe `save_quote_to_db.py` als
  Vorlage.
- Neue API-Endpoints unter `backend/src/routes/agent.py` (für
  Agent-bezogene Aktionen) oder als eigene Route-Datei (für klassische
  CRUD).
- Schema-Änderungen: Models in `backend/src/models/models.py` editieren,
  dann `alembic revision --autogenerate -m "msg"`.

## Lizenz

MIT — siehe [LICENSE](LICENSE).

## Status

Pinta ist im aktiven Pre-Launch-Aufbau (siehe `iteration_logs/` für die
Quote-Qualitäts-Iterationen). Erste Maler-Tests stehen kurz bevor.
