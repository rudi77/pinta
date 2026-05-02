"""Pinta Telegram bot runner.

Wires pytaskforce' built-in TelegramPoller + TelegramOutboundSender to the
Pinta Maler-Agent. No webhook required — long-polling means we just need a
TELEGRAM_BOT_TOKEN in .env and an outbound network path.

Flow per message:
  1. TelegramPoller fetches new messages via getUpdates
  2. Inbound handler creates a fresh Maler-Agent (LeanAgent isn't reusable
     across missions — its message buffer would clobber)
  3. Agent runs the user's text as a mission, session_id = chat_id
  4. Agent's final reply goes back via TelegramOutboundSender

Commands:
  /neu     reset the in-memory chat session (fresh draft)
  <text>   anything else is a mission for the agent
  <photo>  attached as multimodal context — the agent sees the image URL

Run standalone with `scripts/run_telegram_bot.py`. Wire into FastAPI lifespan
once the HTTP backend should run alongside the bot.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from src.agents.factory import create_maler_agent, warm_factory
from src.agents.taskforce_setup import ensure_litellm_env_for_taskforce
from src.core.settings import settings
from src.telegram.state import get_session_for_chat, reset_session_for_chat

logger = logging.getLogger(__name__)


class _NoOpPendingStore:
    """No-op implementation of PendingChannelQuestionStoreProtocol.

    Pinta does not currently use the cross-channel ask_user flow — every
    Telegram message starts a fresh mission. The store is required by
    TelegramPoller's signature; this stub satisfies it without any state.
    """

    async def register(self, **_: Any) -> None:
        return None

    async def resolve(self, **_: Any) -> str | None:
        return None

    async def get_response(self, **_: Any) -> str | None:
        return None

    async def remove(self, **_: Any) -> None:
        return None


def _make_inbound_handler(outbound_sender: Any):
    """Build the per-message handler closing over the outbound sender."""

    async def handle(
        chat_id: str,
        sender_id: str,
        text: str,
        attachments: list[dict[str, Any]] | None,
    ) -> None:
        chat_id_int = int(chat_id) if chat_id.lstrip("-").isdigit() else 0

        # Built-in commands
        stripped = text.strip()
        if stripped.lower() in {"/neu", "/start"}:
            reset_session_for_chat(chat_id_int)
            await outbound_sender.send(
                recipient_id=chat_id,
                message=(
                    "Servus! Ich bin dein Maler-Agent. Beschreib mir das Projekt "
                    "(Räume, Flächen, Vorarbeiten, Material, Termin), und ich "
                    "mach dir einen Kostenvoranschlag.\n\n"
                    "Befehle:\n"
                    "  /neu — neuen Voranschlag starten\n"
                ),
            )
            return

        get_session_for_chat(chat_id_int)  # ensure session exists

        # Multimodal: if a photo arrived, prepend a marker so the agent picks
        # it up. Real vision tool wiring follows in a later iteration.
        mission = stripped or "Bitte analysiere die mitgesendete Datei."
        if attachments:
            n = len(attachments)
            mission = (
                f"[Hinweis: {n} Bild/Dokument vom Nutzer mitgesendet — "
                "visual_estimate-Tool ist noch nicht aktiv, schätze textuell "
                f"oder frag gezielt nach.]\n\n{mission}"
            )

        logger.info(
            "telegram.mission_start chat=%s sender=%s len=%s",
            chat_id, sender_id, len(mission),
        )

        agent = await create_maler_agent()
        try:
            # Send a quick ack so the user sees the bot working — agent
            # execution can take 20-40s for a full quote.
            await outbound_sender.send(
                recipient_id=chat_id,
                message="✏️ Moment, ich rechne...",
            )

            result = await agent.execute(
                mission=mission,
                session_id=f"tg-{chat_id}",
            )
            reply = result.final_message or ""
            if not reply.strip():
                reply = (
                    "Ich konnte die Anfrage gerade nicht beantworten. "
                    "Bitte formulier sie noch mal anders oder schick /neu."
                )
            # Telegram message limit is 4096 chars — chunk if needed
            for chunk in _chunk(reply, 3800):
                await outbound_sender.send(recipient_id=chat_id, message=chunk)
        except Exception as exc:  # pragma: no cover — surfaced to user
            logger.exception("telegram.mission_failed")
            try:
                await outbound_sender.send(
                    recipient_id=chat_id,
                    message=(
                        "Bei der Bearbeitung gab's einen Fehler: "
                        f"{type(exc).__name__}. Bitte nochmal probieren oder /neu."
                    ),
                )
            except Exception:
                pass
        finally:
            try:
                await agent.close()
            except Exception:
                pass

    return handle


def _chunk(text: str, n: int) -> list[str]:
    return [text[i : i + n] for i in range(0, len(text), n)] or [""]


async def run_bot_forever() -> None:
    """Start the Telegram poller and run until cancelled.

    Raises ``RuntimeError`` if no TELEGRAM_BOT_TOKEN is configured — that's
    intentional: the standalone script should fail loudly rather than spin
    silently on no input.
    """
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN ist nicht gesetzt. Trag in .env nach:\n"
            "  TELEGRAM_BOT_TOKEN=<dein BotFather-Token>\n"
            "Bot bei @BotFather erstellen falls noch nicht vorhanden."
        )

    # Set env so any pytaskforce internals reading TELEGRAM_BOT_TOKEN see it
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", token)

    ensure_litellm_env_for_taskforce(strict=True)
    warm_factory()

    from taskforce.infrastructure.communication.outbound_senders import (
        TelegramOutboundSender,
    )
    from taskforce.infrastructure.communication.telegram_poller import (
        TelegramPoller,
    )

    outbound = TelegramOutboundSender(token)
    handler = _make_inbound_handler(outbound)
    poller = TelegramPoller(
        bot_token=token,
        pending_store=_NoOpPendingStore(),
        outbound_sender=outbound,
        recipient_registry=None,
        inbound_message_handler=handler,
    )

    await poller.start()
    logger.info("telegram bot started — long-polling active")
    try:
        # Idle until cancelled (Ctrl-C in standalone, FastAPI shutdown in lifespan)
        await asyncio.Event().wait()
    finally:
        await poller.stop()
        logger.info("telegram bot stopped")
