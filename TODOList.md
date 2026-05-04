# Pinta TODO-Liste

Lebende Status-Übersicht. Erledigtes wird abgehakt aber NICHT gelöscht — die
Liste dient gleichzeitig als Roadmap-Memo. Letzter Stand: 2026-05-04, nach
Commit `b21805c` (`fix(quotes): status update + PDF lookup work for agent
quotes`).

Legende: ✅ done · 🟡 angefangen / unvollständig · ⬜ offen · ❌ verworfen

---

## ✅ Erledigt — v0.1 + Hotfixes

### P0 — PDF-Download & Routing-Fix
- [x] **Login redirected auf `/dashboard`**, nicht mehr `/chat-quote` (`Login.jsx:15`, `App.jsx:91`).
- [x] **Default-Route `/`** zeigt auf `/dashboard`.
- [x] **`apiClient.fetchAgentPdfByQuoteId`** ersetzt das kaputte `downloadQuotePdf`.
- [x] **`GET /api/v1/quotes/{id}/agent-pdf-info`**: Brücke Quote → agent-PDF, sucht zuerst in `Document`-Tabelle, dann FS-Fallback.
- [x] **Legacy `/quotes/{id}/pdf/generate` & `/pdf/download` deprecated**.
- [x] **Tests**: `test_quote_pdf_routes.py` (6 Tests, alle grün).
- [x] **Conftest `test_quote`-Fixture** vom alten `rooms=[]` aufs aktuelle Schema repariert.

### P1 — Migration 007 + Onboarding-Wizard
- [x] **Alembic-Migration 007** (`vat_id`, `logo_path`, `onboarding_completed_at`).
- [x] **User-Model + Schemas** (`UserUpdate`, `UserResponse`, neuer `OnboardingPayload`).
- [x] **Backend-Onboarding-Endpoints**: `GET /onboarding/status`, `POST /onboarding/complete`, `POST /onboarding/logo` (max 1 MB, MIME-Whitelist, Path-Traversal-Defence-in-Depth, relativer logo_path).
- [x] **Frontend-Wizard**: `Onboarding/{OnboardingWizard,Step1Company,Step2CostParams,Step3Logo}.jsx` + Route + Progress-Bar.
- [x] **`useAuth.onboardingComplete`** + Demo-Mode-Bypass.
- [x] **`PrivateRoute`-Gate** redirected nicht-onboardete User auf `/onboarding`.
- [x] **`Register.jsx`** redirected nach Verify auf `/onboarding`.
- [x] **8 Tests** in `test_onboarding.py` (alle grün).

### P2 — UX-Konsolidierung
- [x] **`/quote/new`** als kanonischer Pfad. `/chat-quote` und `/new-quote` redirecten.
- [x] **`QuoteChat.jsx`** ersetzt `ChatQuoteWizard.jsx` (Customer-Form-Dead-Code raus, Multi-File-Upload, Back-Link).
- [x] **`QuoteCreator.jsx`** und altes `frontend-code.txt`-Bundle gelöscht.
- [x] **„KI-Assistent"/„Klassischer Editor"** überall raus, Domänensprache durchgängig.
- [x] **Dashboard-CTA** auf einen Button „Neues Angebot starten".

### P3 — Multimedia
- [x] **MIME-Whitelist erweitert** (`image/heic`, `image/heif`, `image/svg+xml`, `application/octet-stream`) in `routes/ai.py`.
- [x] **Multi-File-Upload** in QuoteChat.
- [x] **`maler.yaml`** Tools-Block prüfen — `multimedia` + `python` aktiv.

### P4 — Quote-Memory (schlank)
- [x] **`agent_service.recent_quotes(limit=5)`**.
- [x] **`build_mission_with_history(prior_quotes=…)`** spliced „Letzte Angebote dieses Nutzers"-Block.
- [x] **`GET /quotes/?q=…`** — Substring-Suche über Kunde/Projekt/Quote-Nummer.
- [x] **Dashboard-Suchfeld** mit 250 ms Debounce + leerer-Treffer-Hinweis.
- [x] **13 Tests** in `test_agent_service.py` + **6 Tests** in `test_quote_search.py` (alle grün).

### P5 — Test-Pyramide + CI
- [x] **MVP-Test-Gate**: 33 deterministische Tests + Smoke + Calculator = 46 grüne Tests.
- [x] **`.github/workflows/ci.yml`**: PYTHONPATH-Fix (`backend/` statt `backend/src`), neuer Frontend-Job mit Playwright/Chromium, MVP-Test-Gate statt All-Tests.
- [x] **`playwright.config.js`**: `npm run dev` statt `pnpm dev` für CI.
- [x] **E2E-Specs aktualisiert** auf neuen Single-Quote-Flow + Onboarding-Gate.
- [x] **Legacy-Klassen-Tests dokumentiert + quarantäniert** (TestUsersIntegration, TestQuotesIntegration etc.).

### v0.1 Release & Tooling
- [x] **CHANGELOG.md** im Keep-a-Changelog-Format mit `[0.1.0]`-Eintrag.
- [x] **Tag `v0.1.0`** lokal + remote.
- [x] **CLAUDE.md** auf 0.1-Stand gehoben.
- [x] **Repo-Cleanup** vor Push (`frontend-code.txt`, Playwright-Reports, MCP-Scratch, scheduled_tasks.lock).
- [x] **`.gitignore`** um Runtime-Artefakte erweitert.

### Hotfixes nach v0.1
- [x] **Frontend-Default-Port 5173 → 5183** (vite, Playwright, Dockerfile, docker-compose, Settings, README, CLAUDE.md). Begründung: Port-Konflikt mit Taskforce-Admin-UI.
- [x] **Provider-aware LLM** (Azure ODER OpenAI auto-detect, `LLM_PROVIDER`-Override). Eigene `backend/agents/llm_config.yaml` mit beiden Aliasen, Runtime-Profile-Renderer in `factory.warm_factory()`.
- [x] **`.env`-Loading**: backend/.env + root/.env (root überschreibt) per pydantic-settings tuple.
- [x] **PUT /quotes/{id} 500 → 200**: Greenlet-Crash beim relationship-Set behoben (`selectinload` statt direkte Zuweisung).
- [x] **`/agent-pdf-info` 404 → 200**: Document-Tabelle als primäre Auflösung statt Filename-Glob.
- [x] **CORS-Header auf Error-Responses** (HTTPException + generic Exception Handler).

---

## 🟡 In Arbeit / Bereits angelegt aber unvollständig

- [x] **Telegram-Bot zuverlässig starten** — Launcher `scripts/start_dev.ps1` öffnet Backend + Bot + Frontend in drei pwsh-Fenstern, setzt `BOT_BACKEND_URL` automatisch passend zum gewählten Port. `scripts/stop_dev.ps1` killt sauber. Verifiziert: Bot `@BluLieferantenBot` ist online und spricht mit Backend auf 8001.
- [ ] **Material-Preise (RAG)**: Tabelle + Service + Tool fertig, **kein Seed**, kein UI zum Pflegen. Agent fällt auf Faustregeln zurück.
- [ ] **Logo-Upload UI fertig, PDF-Rendering ignoriert es** (`generate_quote_pdf.py` zieht `User.logo_path` nicht).

---

## ⬜ MVP-Mindest-Checkliste (Pilot-Reife für 1–4-Mann-Maler)

Stand jetzt: ohne diese Punkte fühlt sich Pinta für echte Tester unvollständig an.

### Telegram & Bot-Pfad
- [x] **Telegram-Bot-Launcher** (`scripts/start_dev.ps1` + `scripts/stop_dev.ps1`).
- [ ] **End-to-End Telegram-Smoke**: echter Bot-Chat mit Foto + PDF-Rückversand mit dem Owner-Account. *Aufwand: 30 min*
- [ ] **Web ↔ Telegram Linking-Token UI**: Endpoint existiert (`/api/v1/agent/linking-token`), aber kein Button im Web-Dashboard zum Generieren des Tokens. *Aufwand: 1 h*

### Owner-UX
- [ ] **Settings-Seite `/settings`**: Stundensatz, Materialaufschlag, Firmendaten, Logo nachträglich editieren. Onboarding-Felder müssen änderbar sein. *Aufwand: 3–4 h*
- [ ] **Quote-Detail: Customer-Felder editierbar**: Name, E-Mail, Telefon, Adresse nachpflegbar. *Aufwand: 2 h*

### PDF-Output (essentiell für Maler-Außenwirkung)
- [ ] **Logo im PDF rendern**: aus `User.logo_path` lesen, oben links platzieren.
- [ ] **Firmen-Header im PDF**: company_name + address + vat_id aus User-Profile in den Briefkopf. *Aufwand: 2 h zusammen*

### Production-Tauglichkeit für Pilot
- [ ] **Email-Verify klären**: SMTP konfigurieren (Pflicht in `DEBUG=false`) ODER Pilot mit `DEBUG=true` betreiben ODER manueller Verify-Endpoint für den Owner. *Aufwand: 30 min*
- [ ] **Phantom-Backend auf Port 8000**: Windows-TCP-Stuck-Listener, blockiert Default-Port. Reboot ODER Backend dauerhaft auf 8001 ODER `netsh int ip reset`. *Aufwand: 5 min*

**Schätzung MVP-Vervollständigung: 8–10 h**

---

## ⬜ Phase-2 — nach Pilot-Feedback (post-MVP)

### Embedding-RAG für Quote-Memory
- [ ] **Migration 008**: `quotes.embedding TEXT` (JSON-serialisiert).
- [ ] **`save_quote_to_db.execute`**: nach Insert Embedding via `litellm.embedding(model="text-embedding-3-small", …)` berechnen.
- [ ] **Neues Tool `search_past_quotes`** (Pattern wie `search_materials.py`): cosine-Similarity gegen User-eigene Quotes.
- [ ] **Tool-Registrierung in `factory.py`** + `maler.yaml`-Tools-Block.
- [ ] **Backfill-Script** für bestehende Quotes.

### Material-Preise pflegbar
- [ ] **`/materials` UI**: Liste + CRUD für eigene Materialpreise.
- [ ] **Embedding-Generierung beim Speichern** (Embed-Service ist da, nur ans UI hängen).
- [ ] **Seed**: 10–20 typische DE/AT-Maler-Materialien als Default-Datenbank.

### Mobile-Optimierung
- [ ] **QuoteChat auf Smartphone testen**: Touch-Targets, Kamera-Direkt-Upload, kleinere Padding.
- [ ] **Mobile-Web-PWA-Manifest**: damit Maler Pinta wie eine App auf den Homescreen ziehen können.

### Multi-Channel-Skalierung
- [ ] **Split-Deployment-fester PDF-Versand**: Telegram-Bot lädt PDF über `/api/v1/agent/pdf/<name>` mit `X-Bot-Service-Token` runter, statt FS-Direktzugriff. Voraussetzung für Bot ≠ Backend-Host.
- [ ] **Inbound Rate-Limiter** vor `/api/v1/agent/bot/chat` (aktuell ungeschützt).
- [ ] **Mehrere Telegram-Bots** pro Channel (für White-Label-Pilot).

---

## ⬜ Tech-Schuld / Polish

### Tests
- [ ] **Pre-existing Klassen-Tests aufräumen**: 122 quarantänierte Tests in `test_users_integration.py`, `test_quotes_integration.py`, `test_auth_integration.py`, `test_ai_integration.py`, `test_documents_integration.py`. Endpoint-für-Endpoint extracten und neu schreiben oder löschen. *Aufwand: 4–6 h*
- [ ] **Integration-Tests für `/api/v1/agent/*`** mit gemocktem AgentService (Plan vorgesehen, noch nicht geschrieben).
- [ ] **E2E-Spec für Onboarding-Flow** (`onboarding.spec.js`): existiert noch nicht, im Plan vorgesehen.
- [ ] **Telegram-Bot-Adapter-Test**: `POST /api/v1/agent/bot/chat` mit gemocktem AgentService.

### Code-Hygiene
- [ ] **`useAuth.demoLogin`/`useAuth.register`** nutzen `localStorage.setItem` direkt statt `apiClient.setToken()` (inkonsistent).
- [ ] **`maler.yaml` System-Prompt** hat noch Telegram-spezifische Anweisungen, könnten kanal-neutral formuliert werden.
- [ ] **Legacy-PDF-Endpoints** (`/quotes/{id}/pdf/{generate,download}`) entfernen, sobald Stripe-Flow verifiziert ist.
- [ ] **Dashboard-Stats** datums-bezogen machen (aktuell zählt „Diesen Monat" einfach `quotes.length`).
- [ ] **Conftest** noch saubere User-Profil-Defaults setzen damit ältere Test-Suiten ohne Anpassung laufen.

### Bugs / Schwachstellen aus Code-Review (offen, nicht-kritisch)
- [ ] **Quota-Race**: parallele `check_user_quota`-Aufrufe können das `quotes_this_month >= 3`-Limit umgehen, wenn beide gleichzeitig prüfen.
- [ ] **`is_paid`-Flow**: Stripe-Webhook-Path nicht durchverifiziert seit dem PDF-Endpoint-Refactor.

---

## ❌ Verworfen / nicht im MVP

- ~~Klassischer 4-Step-Quote-Wizard (`QuoteCreator.jsx`)~~ — durch Single-Chat-Flow ersetzt.
- ~~Apriori-Embedding-RAG für Quotes~~ — schlanker Splice reicht für die ersten 1–4-Mann-Tester.
- ~~„KI-Assistent"-Branding~~ — Domänensprache priorisiert.
- ~~Bilder/Pläne als Phase-2~~ — Multimedia ist im MVP, weil pytaskforce' multimedia-Tool bereits da war.

---

## 📚 Referenzen

- **Plan-File**: `~/.claude/plans/was-m-ssen-wir-noch-delightful-parnas.md`
- **CHANGELOG**: `CHANGELOG.md`
- **Architektur**: `CLAUDE.md`
- **Letzter grüner Commit**: `b21805c`
- **Tag**: `v0.1.0`
