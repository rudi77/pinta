"""Telegram bot adapter — calls the Pinta backend, owns no agent logic.

Stage 3 of the unification: the bot is now a thin shell around the unified
``/api/v1/agent/bot/*`` endpoints. It downloads media via pytaskforce'
TelegramPoller (kept), forwards messages over HTTP, sends back the reply
and any generated PDF. All chat memory + quote persistence lives in the
backend DB.

Wiring:

* TELEGRAM_BOT_TOKEN  — Telegram bot HTTP API
* BOT_SERVICE_TOKEN   — shared secret for X-Bot-Service-Token (must match
                        the one configured in the backend .env)
* BOT_BACKEND_URL     — base URL of the Pinta backend
                        (default http://127.0.0.1:8000)

If BOT_SERVICE_TOKEN or BOT_BACKEND_URL are not configured the bot still
starts but every inbound message gets a "Bot is not configured against the
backend" notice — you'll know within seconds rather than getting silent
errors deep in the agent.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp

from src.agents.taskforce_setup import ensure_litellm_env_for_taskforce
from src.core.settings import settings

logger = logging.getLogger(__name__)


# ── small utils ──────────────────────────────────────────────────────────

def _chunk(text: str, n: int) -> list[str]:
    return [text[i : i + n] for i in range(0, len(text), n)] or [""]


# ── HTTP client wrapping the unified backend ─────────────────────────────

class BackendClient:
    def __init__(self, base_url: str, service_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._token = service_token
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _headers(self, chat_id: str, display_name: str | None) -> dict[str, str]:
        h = {
            "X-Bot-Service-Token": self._token,
            "X-Channel": "telegram",
            "X-External-Id": chat_id,
            "Content-Type": "application/json",
        }
        if display_name:
            h["X-Display-Name"] = display_name
        return h

    async def chat(
        self, chat_id: str, message: str, attachments: list[dict[str, Any]],
        display_name: str | None = None,
    ) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._base}/api/v1/agent/bot/chat"
        payload = {
            "message": message,
            "attachments": [
                {
                    "file_path": a["file_path"],
                    "file_name": a.get("file_name"),
                    "type": a.get("type", "file"),
                }
                for a in attachments if a.get("file_path")
            ],
            "display_name": display_name,
        }
        async with session.post(
            url, json=payload, headers=self._headers(chat_id, display_name),
            timeout=aiohttp.ClientTimeout(total=180),
        ) as resp:
            data = await resp.json()
            if resp.status >= 400:
                logger.warning(
                    "backend.chat status=%s body=%s", resp.status, data,
                )
            return {"_status": resp.status, **data}

    async def reset(self, chat_id: str, display_name: str | None = None) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._base}/api/v1/agent/bot/reset"
        async with session.post(
            url, headers=self._headers(chat_id, display_name),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            try:
                data = await resp.json()
            except Exception:
                data = {}
            return {"_status": resp.status, **data}

    async def link(
        self, chat_id: str, token: str, display_name: str | None = None,
    ) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._base}/api/v1/agent/bot/link"
        async with session.post(
            url,
            json={"token": token, "display_name": display_name},
            headers=self._headers(chat_id, display_name),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            try:
                data = await resp.json()
            except Exception:
                data = {}
            return {"_status": resp.status, **data}


# ── Telegram chat-action (typing indicator) ──────────────────────────────

async def _typing_loop(bot_token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.post(
                        url, json={"chat_id": chat_id, "action": "typing"},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        await resp.read()
                except Exception:
                    pass
                await asyncio.sleep(4)
    except asyncio.CancelledError:
        return


# ── pending-question store stub (poller requires the protocol) ───────────

class _NoOpPendingStore:
    async def register(self, **_: Any) -> None: return None
    async def resolve(self, **_: Any) -> str | None: return None
    async def get_response(self, **_: Any) -> str | None: return None
    async def remove(self, **_: Any) -> None: return None


# ── inbound message handler ──────────────────────────────────────────────

def _make_inbound_handler(
    outbound_sender: Any, backend: BackendClient, bot_token: str,
):
    async def handle(
        chat_id: str, sender_id: str, text: str,
        attachments: list[dict[str, Any]] | None,
    ) -> None:
        stripped = (text or "").strip()
        cmd = stripped.lower().split()[0] if stripped else ""
        display_name = None  # could be enriched from update.from in poller later

        # /neu, /new, /start, /reset
        if cmd in {"/neu", "/new", "/reset"}:
            try:
                await backend.reset(chat_id, display_name=display_name)
            except Exception as exc:
                logger.warning("backend.reset failed: %s", exc)
            await outbound_sender.send(
                recipient_id=chat_id,
                message=(
                    "Servus, ich bin Manfred — dein Maler-Meister-Agent. 👷\n\n"
                    "Erzähl mir vom Projekt: was, wo, wieviel Quadratmeter, "
                    "Zustand, bis wann. Foto vom Raum kannst du auch direkt "
                    "schicken.\n\n"
                    "Befehle: /neu — frischer Auftrag · "
                    "/link <token> — Bot mit Pinta-Account verknüpfen"
                ),
            )
            return

        if cmd == "/start":
            # /start <token> in Telegram is the deep-link case; without a
            # token argument we behave like /neu.
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2 and len(parts[1]) >= 8:
                token = parts[1].strip()
                resp = await backend.link(chat_id, token, display_name=display_name)
                if resp.get("success"):
                    await outbound_sender.send(
                        recipient_id=chat_id,
                        message=(
                            "✅ Verknüpft mit deinem Pinta-Account "
                            f"({resp.get('username')}).\n"
                            "Alle neuen Quotes landen ab jetzt auch im Web-Dashboard."
                        ),
                    )
                else:
                    await outbound_sender.send(
                        recipient_id=chat_id,
                        message=(
                            "⚠️ Linking-Token ist unbekannt oder abgelaufen. "
                            "Erzeug im Web-Dashboard ein neues und versuch's "
                            "noch mal."
                        ),
                    )
                return
            # plain /start fallthrough to greeting
            try:
                await backend.reset(chat_id, display_name=display_name)
            except Exception as exc:
                logger.warning("backend.reset failed: %s", exc)
            await outbound_sender.send(
                recipient_id=chat_id,
                message=(
                    "Servus, ich bin Manfred. Beschreib mir dein Projekt, "
                    "ich mach dir einen Voranschlag.\n\n"
                    "Hast du schon einen Pinta-Account? Dann verknüpf den "
                    "Chat mit /link <token> — Token findest du im Dashboard."
                ),
            )
            return

        # /link <token> direct command
        if cmd == "/link":
            parts = stripped.split(maxsplit=1)
            if len(parts) != 2 or len(parts[1]) < 8:
                await outbound_sender.send(
                    recipient_id=chat_id,
                    message=(
                        "Format: /link <token>\n"
                        "Den Token erzeugst du im Pinta-Dashboard unter "
                        "'Telegram verbinden'."
                    ),
                )
                return
            resp = await backend.link(chat_id, parts[1].strip(), display_name=display_name)
            if resp.get("success"):
                await outbound_sender.send(
                    recipient_id=chat_id,
                    message=(
                        "✅ Verknüpft mit deinem Pinta-Account "
                        f"({resp.get('username')})."
                    ),
                )
            else:
                await outbound_sender.send(
                    recipient_id=chat_id,
                    message="⚠️ Token unbekannt oder abgelaufen.",
                )
            return

        # Regular message
        message = stripped or "(Datei ohne Text)"
        atts = attachments or []
        # Strip data-only attachments (no file_path) — backend can't reach
        # base64 blobs from the bot's process anyway.
        atts = [a for a in atts if a.get("file_path")]

        logger.info(
            "telegram.mission_start chat=%s sender=%s len=%s atts=%s",
            chat_id, sender_id, len(message), len(atts),
        )

        typing_task = asyncio.create_task(
            _typing_loop(bot_token, chat_id),
            name=f"telegram-typing-{chat_id}",
        )
        try:
            resp = await backend.chat(chat_id, message, atts, display_name=display_name)
        except Exception as exc:
            logger.exception("backend.chat raised")
            resp = {"_status": 599, "detail": f"{type(exc).__name__}: {exc}"}
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except Exception:
                pass

        if resp.get("_status", 500) >= 400:
            err = resp.get("detail") or "unbekannter Fehler"
            await outbound_sender.send(
                recipient_id=chat_id,
                message=f"Beim Bearbeiten ist ein Fehler aufgetreten: {err}",
            )
            return

        reply = resp.get("humanized_message") or resp.get("final_message") or ""
        if not reply.strip():
            reply = (
                "Hmm, da ist mir die Antwort gerade verloren gegangen. "
                "Frag nochmal — oder schick /neu, dann starten wir frisch."
            )
        for chunk in _chunk(reply, 3800):
            await outbound_sender.send(recipient_id=chat_id, message=chunk)

        # Ship the PDF if the backend produced one. The PDF lives on the
        # backend host's filesystem; in a true split deployment we'd download
        # it via /api/v1/agent/pdf/<name> — for now bot and backend share
        # the same .taskforce_maler/quotes/ directory, so the local path
        # works directly.
        pdf_filename = resp.get("pdf_filename")
        if pdf_filename:
            local_path = (
                Path(__file__).resolve().parents[2]
                / ".taskforce_maler" / "quotes" / pdf_filename
            )
            if local_path.is_file():
                try:
                    await outbound_sender.send_file(
                        recipient_id=chat_id,
                        file_path=str(local_path),
                        attachment_type="document",
                        caption="📄 Kostenvoranschlag als PDF",
                    )
                except Exception as exc:
                    logger.exception("telegram.send_file_failed")
                    await outbound_sender.send(
                        recipient_id=chat_id,
                        message=f"(PDF-Versand fehlgeschlagen: {type(exc).__name__})",
                    )
            else:
                logger.warning("telegram.pdf_missing_local path=%s", local_path)

    return handle


# ── lifecycle ────────────────────────────────────────────────────────────

async def run_bot_forever() -> None:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN fehlt in .env. Bei @BotFather erzeugen "
            "und in .env eintragen."
        )
    bot_service_token = (settings.bot_service_token or "").strip()
    if not bot_service_token:
        raise RuntimeError(
            "BOT_SERVICE_TOKEN fehlt in .env. Generiere ein langes Secret "
            "(z.B. python -c 'import secrets; print(secrets.token_urlsafe(32))') "
            "und setz es in .env (Backend UND Bot lesen dieselbe Datei)."
        )
    backend_url = (settings.bot_backend_url or "http://127.0.0.1:8000").rstrip("/")

    # Set env so any pytaskforce internals reading TELEGRAM_BOT_TOKEN see it
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", token)

    # Bridge env so the bot still validates Azure config presence — the
    # actual agent calls happen in the BACKEND now, but failing early is
    # nicer than silently 500-ing on the first message.
    try:
        ensure_litellm_env_for_taskforce(strict=False)
    except Exception as exc:
        logger.warning("Azure env bridge: %s", exc)

    from taskforce.infrastructure.communication.outbound_senders import (
        TelegramOutboundSender,
    )
    from taskforce.infrastructure.communication.telegram_poller import (
        TelegramPoller,
    )

    backend = BackendClient(backend_url, bot_service_token)
    outbound = TelegramOutboundSender(token)
    handler = _make_inbound_handler(outbound, backend, bot_token=token)
    poller = TelegramPoller(
        bot_token=token,
        pending_store=_NoOpPendingStore(),
        outbound_sender=outbound,
        recipient_registry=None,
        inbound_message_handler=handler,
    )

    await poller.start()
    logger.info(
        "telegram bot started — long-polling, backend=%s",
        backend_url,
    )
    try:
        await asyncio.Event().wait()
    finally:
        await poller.stop()
        await backend.close()
        logger.info("telegram bot stopped")
