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
import json
import logging
import os
import re
from typing import Any

from pathlib import Path

from src.agents.factory import create_maler_agent, warm_factory
from src.agents.taskforce_setup import ensure_litellm_env_for_taskforce
from src.core.settings import settings
from src.telegram import conversation_log
from src.telegram.state import get_session_for_chat, reset_session_for_chat

# Where the generate_quote_pdf tool writes finished PDFs.
_QUOTES_DIR = (
    Path(__file__).resolve().parents[2] / ".taskforce_maler" / "quotes"
)


def _snapshot_pdfs() -> set[Path]:
    if not _QUOTES_DIR.exists():
        return set()
    return {p for p in _QUOTES_DIR.glob("*.pdf") if p.is_file()}


def _newest(paths: set[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def _humanize_reply(raw: str) -> str:
    """Strip raw JSON / code fences and return a Maler-friendly summary.

    The agent is instructed (in maler.yaml) to write a short German summary
    only — no JSON, no code blocks. This is a defensive net for runs where
    the LLM still leaks the internal quote envelope into the chat.
    """
    if not raw or not raw.strip():
        return raw

    text = raw.strip()

    # Find a balanced JSON object that looks like a quote envelope.
    # Try greedy first (outermost {...}) so nested item dicts don't shadow
    # the wrapper, then fall back to non-greedy if the outermost match
    # isn't valid JSON (e.g. mid-message braces).
    quote = None
    for pattern in (r"\{[\s\S]*\}", r"\{[\s\S]*?\}"):
        for match in re.finditer(pattern, text):
            snippet = match.group(0)
            try:
                obj = json.loads(snippet)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and (
                "items" in obj or "total_amount" in obj or "subtotal" in obj
            ):
                quote = obj
                break
        if quote:
            break

    # Strip all fenced code blocks (```...```).
    cleaned = re.sub(r"```[\s\S]*?```", "", text).strip()
    # Strip any standalone JSON-looking braces blocks (top-level only).
    cleaned = re.sub(
        r"^\s*\{[\s\S]*?\}\s*$", "", cleaned, flags=re.MULTILINE
    ).strip()

    if quote:
        title = quote.get("project_title") or "Kostenvoranschlag"
        sub = quote.get("subtotal")
        vat = quote.get("vat_amount")
        total = quote.get("total_amount")

        def _fmt(v):
            try:
                return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (TypeError, ValueError):
                return "—"

        summary_lines = [title]
        if sub is not None and vat is not None and total is not None:
            summary_lines.append(
                f"Netto: {_fmt(sub)} EUR · MwSt 19%: {_fmt(vat)} EUR · "
                f"Brutto: {_fmt(total)} EUR"
            )
        notes = (quote.get("notes") or "").strip()
        if notes:
            short = notes.split(".")[0].strip()
            if short:
                summary_lines.append(short + ".")
        summary_lines.append("📄 PDF kommt gleich als Download.")

        # If the model wrote a useful prose preamble alongside the JSON,
        # keep that — but only if it doesn't contain raw JSON itself.
        if cleaned and "{" not in cleaned and "}" not in cleaned and len(cleaned) < 600:
            return cleaned + "\n\n" + "\n".join(summary_lines)
        return "\n".join(summary_lines)

    # No quote JSON detected — just return the cleaned prose, falling back
    # to the original if cleaning ate everything.
    return cleaned or raw

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


def _make_inbound_handler(outbound_sender: Any, bot_token: str):
    """Build the per-message handler closing over the outbound sender."""

    async def handle(
        chat_id: str,
        sender_id: str,
        text: str,
        attachments: list[dict[str, Any]] | None,
    ) -> None:
        chat_id_int = int(chat_id) if chat_id.lstrip("-").isdigit() else 0

        # Built-in commands (lowercase aliases)
        stripped = text.strip()
        cmd = stripped.lower().split()[0] if stripped else ""
        if cmd in {"/neu", "/new", "/start", "/reset"}:
            reset_session_for_chat(chat_id_int)
            conversation_log.clear(chat_id)
            await outbound_sender.send(
                recipient_id=chat_id,
                message=(
                    "Servus, ich bin Manfred — dein Maler-Meister-Agent. 👷\n\n"
                    "Erzähl mir vom Projekt: was, wo, wieviel Quadratmeter, "
                    "in welchem Zustand, bis wann. Foto vom Raum darfst du "
                    "auch direkt schicken, das hilft beim Schätzen.\n\n"
                    "Wenn alles klar ist, schmeiß ich dir einen "
                    "Kostenvoranschlag als PDF zurück.\n\n"
                    "Befehle: /neu — frischer Auftrag"
                ),
            )
            return

        get_session_for_chat(chat_id_int)  # ensure session exists

        # Build the mission. Attachments come from the TelegramPoller already
        # downloaded — photos arrive with a temp ``file_path``, documents the
        # same. We tell the agent the local path and which tool to use, so it
        # can call ``multimedia`` itself to inspect the file.
        new_user_text = stripped or "Der Nutzer hat eine Datei ohne Begleittext geschickt."
        if attachments:
            attach_lines = ["Der Nutzer hat folgende Datei(en) mitgeschickt — "
                            "lies sie mit dem `multimedia`-Tool ein, bevor du "
                            "antwortest:"]
            for att in attachments:
                fp = att.get("file_path")
                fn = att.get("file_name") or "datei"
                kind = att.get("type") or "file"
                if fp:
                    attach_lines.append(f"- {kind}: `{fp}` (Dateiname: {fn})")
                else:
                    attach_lines.append(f"- {kind}: (kein Pfad — Foto nur als data_url)")
            new_user_text = "\n".join(attach_lines) + "\n\n" + new_user_text

        # Inject prior turns so the agent has chat-level memory.
        mission = conversation_log.build_mission_with_history(chat_id, new_user_text)

        logger.info(
            "telegram.mission_start chat=%s sender=%s len=%s attachments=%s",
            chat_id, sender_id, len(mission),
            len(attachments) if attachments else 0,
        )

        # Persist the user's turn now (before the agent runs) so a crash
        # mid-mission still leaves a coherent transcript.
        conversation_log.append(chat_id, "user", new_user_text)

        agent = await create_maler_agent()
        try:
            # Show "is typing…" instead of a separate text message — far less
            # spammy and adapts naturally to short replies vs long quote
            # generations. We re-trigger it during the run because Telegram
            # auto-clears typing after ~5s.
            typing_task = asyncio.create_task(
                _typing_loop(bot_token, chat_id),
                name=f"telegram-typing-{chat_id}",
            )

            # Snapshot existing PDFs so we can detect new ones the agent
            # generated during this mission, regardless of whether the path
            # propagated up through the stream.
            pdfs_before = _snapshot_pdfs()

            # Stream the run so we can intercept generate_quote_pdf's tool_result
            # and ship the PDF as a Telegram attachment afterwards.
            final_message = ""
            pdf_path: str | None = None

            async for event in agent.execute_stream(
                mission=mission,
                session_id=f"tg-{chat_id}",
            ):
                etype = (
                    event.event_type.value
                    if hasattr(event.event_type, "value")
                    else str(event.event_type)
                )
                if etype == "tool_result":
                    found = _extract_pdf_path(event.data)
                    if found:
                        pdf_path = found
                elif etype == "final_answer":
                    final_message = (
                        event.data.get("content")
                        or event.data.get("final_message")
                        or final_message
                    )
                elif etype == "complete":
                    final_message = event.data.get("final_message") or final_message
                elif etype == "error":
                    err = event.data.get("message") or event.data.get("error")
                    logger.warning("telegram.agent_error %s", err)

            # Filesystem fallback: if the stream-side detection missed it
            # (event shape variations across pytaskforce versions, python-
            # bridge wrapping, etc.) but a new PDF appeared in the quotes
            # directory during this run, send the newest one.
            if not pdf_path:
                new_pdfs = _snapshot_pdfs() - pdfs_before
                newest = _newest(new_pdfs)
                if newest:
                    pdf_path = str(newest)
                    logger.info(
                        "telegram.pdf_via_fs_fallback chat=%s path=%s",
                        chat_id, pdf_path,
                    )

            typing_task.cancel()
            try:
                await typing_task
            except (asyncio.CancelledError, Exception):
                pass

            reply = _humanize_reply(final_message or "")
            if not reply.strip():
                reply = (
                    "Hmm, da ist mir gerade die Antwort verloren gegangen. "
                    "Frag nochmal — oder schick /neu, dann starten wir frisch."
                )
            # Persist the assistant turn so the next message has it as context.
            conversation_log.append(chat_id, "assistant", reply)
            # Telegram message limit is 4096 chars — chunk if needed
            for chunk in _chunk(reply, 3800):
                await outbound_sender.send(recipient_id=chat_id, message=chunk)

            # If the agent generated a PDF, ship it as a downloadable document.
            if pdf_path:
                try:
                    await outbound_sender.send_file(
                        recipient_id=chat_id,
                        file_path=pdf_path,
                        attachment_type="document",
                        caption="📄 Kostenvoranschlag als PDF",
                    )
                    logger.info(
                        "telegram.pdf_sent chat=%s path=%s", chat_id, pdf_path,
                    )
                except FileNotFoundError:
                    logger.warning("telegram.pdf_missing path=%s", pdf_path)
                    await outbound_sender.send(
                        recipient_id=chat_id,
                        message=(
                            "(Hinweis: Das PDF konnte ich gerade nicht anhängen — "
                            "der Agent hat den Pfad zwar gemeldet, die Datei ist "
                            "aber nicht da.)"
                        ),
                    )
                except Exception as exc:
                    logger.exception("telegram.send_file_failed")
                    await outbound_sender.send(
                        recipient_id=chat_id,
                        message=(
                            "(Hinweis: PDF-Versand fehlgeschlagen: "
                            f"{type(exc).__name__})."
                        ),
                    )
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


async def _typing_loop(bot_token: str, chat_id: str) -> None:
    """Repeatedly fire ``sendChatAction: typing`` so Telegram keeps the
    "is typing…" indicator visible until the agent's reply lands.

    Telegram auto-clears the indicator after ~5 seconds; we re-trigger every
    4 seconds. Cancelled by the caller right before sending the actual reply.
    """
    import aiohttp
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.post(
                        url,
                        json={"chat_id": chat_id, "action": "typing"},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        await resp.read()
                except Exception:
                    pass  # transient network errors are fine — keep looping
                await asyncio.sleep(4)
    except asyncio.CancelledError:
        return


def _extract_pdf_path(event_data: dict) -> str | None:
    """Pull a generate_quote_pdf file_path out of any tool_result payload.

    Scans the dict tree recursively: the agent often calls the PDF tool via
    the python-bridge (``tool_generate_quote_pdf(...)``), in which case the
    stream event arrives as ``tool=python`` with the real PDF result nested
    one level deeper under ``result.result``. Filtering on tool_name would
    miss that — instead we just look for any ``{success: true, file_path:
    "*.pdf"}`` shape anywhere in the payload.
    """
    if not isinstance(event_data, dict):
        return None

    seen: set[int] = set()

    def _walk(node):
        if isinstance(node, dict):
            if id(node) in seen:
                return None
            seen.add(id(node))
            fp = node.get("file_path")
            if (
                node.get("success") is True
                and isinstance(fp, str)
                and fp.lower().endswith(".pdf")
            ):
                return fp
            for v in node.values():
                hit = _walk(v)
                if hit:
                    return hit
        elif isinstance(node, list):
            for item in node:
                hit = _walk(item)
                if hit:
                    return hit
        return None

    return _walk(event_data)


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
    handler = _make_inbound_handler(outbound, bot_token=token)
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
