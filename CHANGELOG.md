# Changelog

All notable changes to Pinta are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows
[SemVer](https://semver.org/spec/v2.0.0.html). Pre-1.0 releases (`0.x`) may
include breaking changes between minor versions while the MVP shape settles.

## [Unreleased]

## [0.1.0] — 2026-05-04

The first cut suitable for friendly piloting by 1–4-person painting
businesses. The web app, the Telegram bot, and the FastAPI backend now
share a single quote-creation path through the unified agent endpoint;
new users go through a mandatory three-step onboarding before they can
reach the dashboard.

### Added
- **Mandatory onboarding wizard** for new users — three steps (company
  details → cost parameters → optional logo) with a hard gate in
  `PrivateRoute` so the dashboard is unreachable until
  `User.onboarding_completed_at` is set.
- **Onboarding API**: `GET /api/v1/onboarding/status`,
  `POST /api/v1/onboarding/complete`, `POST /api/v1/onboarding/logo`
  (PNG/JPEG/WebP/SVG, 1 MB cap, path-traversal-protected).
- **User profile fields**: `vat_id`, `logo_path`,
  `onboarding_completed_at` (Alembic migration `007`).
- **Quote-memory splice** — the agent receives the user's last 5 quotes
  as a "Letzte Angebote dieses Nutzers" context block in every mission.
- **Quote search** — `GET /api/v1/quotes/?q=…` does a case-insensitive
  substring match across customer name, project title, and quote
  number; surfaced as a search field on the dashboard.
- **Quote → agent-PDF resolver** — `GET /api/v1/quotes/{id}/agent-pdf-info`
  bridges old quote records to the new agent PDF directory; replaces
  the broken `apiClient.downloadQuotePdf` flow.
- **Frontend onboarding components**: `Onboarding/OnboardingWizard`,
  `Step1Company`, `Step2CostParams`, `Step3Logo`.
- **Test gate in CI** — separate `frontend` job runs Playwright with
  Chromium, backend job runs the deterministic MVP test suite.
- **New backend test suites**: `test_agent_service`,
  `test_quote_pdf_routes`, `test_onboarding`, `test_quote_search`
  (33 deterministic tests, no live LLM dependency).

### Changed
- **Login lands on `/dashboard`**, not `/chat-quote`. The default route
  `/` now redirects to `/dashboard` instead of the quote chat.
- **Single quote-creation flow** at `/quote/new` (`QuoteChat.jsx`).
  `/chat-quote` and `/new-quote` redirect to the canonical path.
  Customer-form dead code removed; multi-file upload accepted.
- **Domain-language UX** — the CTA "Klassischer Editor" / "KI-Assistent"
  pair on the dashboard is replaced by a single "Neues Angebot
  starten" button. The "KI-Konversationsverlauf" header on the quote
  detail page is now "Chat-Verlauf"; "KI-Assistent" / "Nutzer" labels
  become "Pinta" / "Du".
- **Document-upload MIME whitelist** widened (`image/heic`, `image/heif`,
  `image/gif`, `image/svg+xml`, `application/octet-stream`) so HEIC
  photos from Telegram users no longer get rejected.
- **`UserUpdate` schema** now exposes `vat_id`; `UserResponse` adds
  `vat_id`, `logo_path`, `onboarding_completed_at`.
- **`build_mission_with_history`** accepts `prior_quotes`; mission
  prompts are augmented with quote-memory before chat history.
- **CI** — `PYTHONPATH` switched from `backend/src` to `backend/` to
  match `from src.core...` imports; new MVP test gate replaces the
  whole-suite run while legacy class-based suites remain quarantined.
- **`backend/tests/conftest.py::test_quote`** fixture corrected to use
  `project_title` / `labor_hours` instead of the removed `rooms`
  column. Onboarding router registered in the test app.
- **Playwright config** uses `npm run dev` instead of `pnpm dev` so CI
  can run the suite without an extra package-manager install step.

### Fixed
- **PDF download for agent-generated quotes** — the legacy
  `/quotes/{id}/pdf/generate` path looked in `uploads/pdfs/` and
  returned 404 for any quote produced by the unified agent (which
  writes to `.taskforce_maler/quotes/`). The frontend now resolves PDFs
  through `GET /quotes/{id}/agent-pdf-info` and downloads via the
  existing `GET /api/v1/agent/pdf/{name}` (auth-gated, path-traversal
  protected).
- **Memory leak on PDF download** — `URL.createObjectURL` is now
  revoked in a `finally` block so a failed `link.click()` no longer
  leaves the blob alive.
- **Onboarding logo path traversal** — defence-in-depth check after
  filename sanitisation; logo path stored relative to the uploads
  root rather than as an absolute filesystem path.
- **`refreshUser` failure traps user on onboarding screen** — a
  transient error after a successful `POST /onboarding/complete` no
  longer prevents the navigation to `/dashboard`.

### Deprecated
- `POST /api/v1/quotes/{id}/pdf/generate` and
  `GET /api/v1/quotes/{id}/pdf/download` — replaced by
  `GET /api/v1/quotes/{id}/agent-pdf-info` →
  `GET /api/v1/agent/pdf/{name}`. The legacy paths still resolve and
  return their original 4xx/5xx contract; they are scheduled for
  removal in 0.2.

### Removed
- `frontend/src/components/QuoteCreator.jsx` (classical 4-step quote
  wizard, replaced by the chat-only flow).
- `frontend/src/components/ChatQuoteWizard.jsx` (renamed to
  `QuoteChat.jsx`; customer-form dead code dropped along the way).
- `frontend/frontend-code.txt` (legacy bundled-source dump that wasn't
  used by anything).
- `apiClient.downloadQuotePdf` (replaced by `fetchAgentPdfByQuoteId`).

[Unreleased]: https://github.com/rudi77/pinta/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rudi77/pinta/releases/tag/v0.1.0
