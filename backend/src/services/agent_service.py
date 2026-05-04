"""Pinta-side wrapper around the pytaskforce Maler-Agent.

This is the central service that BOTH the Web App and the Telegram-Bot
talk to. It owns:

* The shared ``AgentFactory`` (warmed once at startup).
* The chat-memory layer — stored in the Pinta DB (``Conversation`` /
  ``ConversationMessage``), not in the agent's local FS state.
* The unique ``session_id`` per conversation that pytaskforce uses for its
  internal planner/state.

The runtime contract:

    service = AgentService()
    await service.start()                    # warm factory
    result = await service.chat(user, "...") # one-shot mission

    async for ev in service.chat_stream(user, "..."):  # streaming
        ...

    await service.reset(user)                # /neu equivalent
"""
from __future__ import annotations

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.factory import create_maler_agent, warm_factory
from src.models.models import Conversation, ConversationMessage, Quote, User

logger = logging.getLogger(__name__)

# How many recent turns to splice into the next mission. The agent's
# internal MessageHistoryManager doesn't accept a prior-messages parameter,
# so we inject context as a plain prefix in the mission string.
_MAX_HISTORY_TURNS = 8
_MAX_HISTORY_CHARS_PER_TURN = 1500
# How many of the user's most recent saved quotes to splice into a new
# mission as a "you priced these recently" prompt — schlankes Memory.
_QUOTE_MEMORY_LIMIT = 5

# Where generate_quote_pdf writes finished PDFs (also used by the FS-fallback
# detection in the runner / chat endpoint).
_QUOTES_DIR = (
    Path(__file__).resolve().parents[2] / ".taskforce_maler" / "quotes"
)


class AgentService:
    """Stateless façade: every method takes the user; per-call DB session."""

    def __init__(self) -> None:
        self._warmed = False

    async def start(self) -> None:
        """Warm the AgentFactory once at FastAPI startup."""
        if self._warmed:
            return
        warm_factory()
        self._warmed = True
        logger.info("agent_service.warmed")

    # ── conversation CRUD ────────────────────────────────────────────────

    async def get_active_conversation(
        self, db: AsyncSession, user: User, *, channel: str = "web",
        create_if_missing: bool = True,
    ) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .where(Conversation.is_active == True)  # noqa: E712
            .order_by(Conversation.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv is None and create_if_missing:
            conv = Conversation(user_id=user.id, channel=channel, is_active=True)
            db.add(conv)
            await db.flush()
        return conv

    async def reset(
        self, db: AsyncSession, user: User, *, channel: str = "web",
    ) -> Conversation:
        """Archive the active conversation and start a fresh one."""
        existing = await self.get_active_conversation(
            db, user, channel=channel, create_if_missing=False,
        )
        if existing is not None:
            existing.is_active = False
            existing.archived_at = datetime.utcnow()

        fresh = Conversation(user_id=user.id, channel=channel, is_active=True)
        db.add(fresh)
        await db.flush()
        await db.commit()
        return fresh

    async def append_message(
        self, db: AsyncSession, conversation: Conversation,
        *, role: str, content: str, extra_metadata: Optional[str] = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            extra_metadata=extra_metadata,
        )
        db.add(msg)
        # Keep the conversation's updated_at fresh
        conversation.updated_at = datetime.utcnow()
        await db.flush()
        return msg

    async def recent_messages(
        self, db: AsyncSession, conversation: Conversation,
        *, limit: int = _MAX_HISTORY_TURNS,
    ) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def recent_quotes(
        self, db: AsyncSession, user: User,
        *, limit: int = _QUOTE_MEMORY_LIMIT,
    ) -> list[Quote]:
        stmt = (
            select(Quote)
            .where(Quote.user_id == user.id)
            .order_by(Quote.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ── mission building ─────────────────────────────────────────────────

    @staticmethod
    def build_mission_with_history(
        prior_messages: list[ConversationMessage], new_user_text: str,
        *, prior_quotes: Optional[list[Quote]] = None,
    ) -> str:
        sections: list[str] = []

        if prior_quotes:
            sections.append(
                "Letzte Angebote dieses Nutzers (zur Orientierung bei "
                "Preisen / Stil — KEIN Auftrag, nur Kontext):"
            )
            for q in prior_quotes:
                created = q.created_at.strftime("%Y-%m-%d") if q.created_at else "—"
                customer = (q.customer_name or "—").strip() or "—"
                title = (q.project_title or "—").strip() or "—"
                total = q.total_amount if q.total_amount is not None else 0.0
                sections.append(
                    f"- {q.quote_number}: {title}, Brutto {total:.2f} EUR, "
                    f"am {created}, Kunde {customer}"
                )
            sections.append("")

        if prior_messages:
            sections.append("Bisheriger Chat-Verlauf (älteste zuerst, gekürzt):")
            for m in prior_messages:
                role = "Nutzer" if m.role == "user" else "Du"
                content = (m.content or "").strip()
                if len(content) > _MAX_HISTORY_CHARS_PER_TURN:
                    content = content[: _MAX_HISTORY_CHARS_PER_TURN - 1] + "…"
                sections.append(f"- **{role}:** {content}")
            sections.append("")

        if not sections:
            return new_user_text

        sections.append("Aktuelle Nachricht des Nutzers:")
        sections.append(new_user_text)
        return "\n".join(sections)

    @staticmethod
    def session_id_for(conversation: Conversation) -> str:
        # pytaskforce session_id needs to be stable per conversation so the
        # agent's planner state survives between turns. We embed the conv id
        # so different conversations don't share state.
        return f"pinta-conv-{conversation.id}"

    # ── PDF detection (filesystem fallback) ──────────────────────────────

    @staticmethod
    def snapshot_pdfs() -> set[Path]:
        if not _QUOTES_DIR.exists():
            return set()
        return {p for p in _QUOTES_DIR.glob("*.pdf") if p.is_file()}

    @staticmethod
    def newest_pdf(paths: set[Path]) -> Optional[Path]:
        if not paths:
            return None
        return max(paths, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def extract_pdf_path_from_event(event_data: Any) -> Optional[str]:
        """Recursive scan for {success: True, file_path: '*.pdf'}."""
        seen: set[int] = set()

        def _walk(node: Any) -> Optional[str]:
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

    @staticmethod
    def extract_quote_ref_from_event(
        event_data: Any,
    ) -> Optional[tuple[int, Optional[str]]]:
        """Recursive scan for {success: True, quote_id: int, quote_number: str?}."""
        seen: set[int] = set()

        def _walk(node: Any) -> Optional[tuple[int, Optional[str]]]:
            if isinstance(node, dict):
                if id(node) in seen:
                    return None
                seen.add(id(node))
                qid = node.get("quote_id")
                if node.get("success") is True and isinstance(qid, int):
                    qnum = node.get("quote_number")
                    return (qid, qnum if isinstance(qnum, str) else None)
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

    # ── one-shot chat ────────────────────────────────────────────────────

    async def chat(
        self, db: AsyncSession, user: User, mission_text: str,
        *, channel: str = "web", attachments_block: str = "",
    ) -> dict[str, Any]:
        """Run one mission. Returns {final_message, pdf_path?, conversation_id, status}."""
        await self.start()
        conv = await self.get_active_conversation(db, user, channel=channel)
        prior = await self.recent_messages(db, conv)
        prior_quotes = await self.recent_quotes(db, user)

        body = (
            f"{attachments_block}\n\n{mission_text}".strip()
            if attachments_block else mission_text
        )
        mission = self.build_mission_with_history(prior, body, prior_quotes=prior_quotes)

        # Persist the user turn BEFORE running so a crash mid-mission
        # still leaves a coherent transcript.
        await self.append_message(db, conv, role="user", content=mission_text)
        await db.commit()

        pdfs_before = self.snapshot_pdfs()
        agent = await create_maler_agent()
        from src.agents.tools.save_quote_to_db import (
            current_conversation_id,
            current_quote_id,
            current_user_id,
        )
        user_token = current_user_id.set(user.id)
        conv_token = current_conversation_id.set(conv.id)
        quote_token = current_quote_id.set(None)
        pdf_path: Optional[str] = None
        quote_id: Optional[int] = None
        quote_number: Optional[str] = None
        final_message = ""
        status = "completed"
        try:
            async for event in agent.execute_stream(
                mission=mission, session_id=self.session_id_for(conv),
            ):
                etype = (
                    event.event_type.value
                    if hasattr(event.event_type, "value")
                    else str(event.event_type)
                )
                if etype == "tool_result":
                    found = self.extract_pdf_path_from_event(event.data)
                    if found:
                        pdf_path = found
                    qref = self.extract_quote_ref_from_event(event.data)
                    if qref is not None:
                        quote_id, quote_number = qref
                elif etype == "final_answer":
                    final_message = (
                        event.data.get("content")
                        or event.data.get("final_message")
                        or final_message
                    )
                elif etype == "complete":
                    final_message = event.data.get("final_message") or final_message
                elif etype == "error":
                    status = "error"
                    logger.warning(
                        "agent_service.agent_error user=%s err=%s",
                        user.id, event.data.get("message") or event.data.get("error"),
                    )

            if not pdf_path:
                new_pdfs = self.snapshot_pdfs() - pdfs_before
                newest = self.newest_pdf(new_pdfs)
                if newest:
                    pdf_path = str(newest)
        finally:
            try:
                await agent.close()
            except Exception:
                pass
            current_quote_id.reset(quote_token)
            current_conversation_id.reset(conv_token)
            current_user_id.reset(user_token)

        # Fallback-Antwort: wenn der Agent leer zurückkommt aber im python-
        # Tool tatsächlich ein Quote-Dict berechnet hat, nutzen wir das.
        # Häufigste Ursache: Azure Content-Filter blockt das finale Summary
        # oder max_steps lief ab — der eigentliche Quote ist aber da.
        if (not final_message or not final_message.strip()) and pdf_path:
            final_message = (
                "Kostenvoranschlag fertig — PDF folgt gleich. "
                "(Hinweis: die Text-Zusammenfassung wurde vom Provider "
                "blockiert, der Quote selbst ist in Ordnung.)"
            )
        elif not final_message or not final_message.strip():
            if status == "error":
                final_message = (
                    "Hmm, da hat mich der KI-Provider mittendrin gestoppt "
                    "(meist Content-Filter oder zu komplexe Anfrage). "
                    "Probier's nochmal mit anderen Worten oder schick /neu "
                    "für einen frischen Versuch."
                )
            else:
                final_message = (
                    "Erzähl mir mehr über das Projekt — Räume, Flächen, Material."
                )

        # Persist the assistant turn (raw — humanization is the channel
        # adapter's responsibility, since e.g. Web wants markdown and
        # Telegram wants stripped JSON).
        await self.append_message(
            db, conv, role="assistant", content=final_message or "",
            extra_metadata=(
                json.dumps({"pdf_path": pdf_path}, ensure_ascii=False)
                if pdf_path else None
            ),
        )
        await db.commit()

        return {
            "conversation_id": conv.id,
            "final_message": final_message,
            "pdf_path": pdf_path,
            "quote_id": quote_id,
            "quote_number": quote_number,
            "status": status,
        }

    # ── streaming chat ───────────────────────────────────────────────────

    async def chat_stream(
        self, db: AsyncSession, user: User, mission_text: str,
        *, channel: str = "web", attachments_block: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield agent stream events as plain dicts. Persists turns when done.

        Each yielded dict has ``type`` (matches StreamEvent.event_type) and
        ``data``. Plus a final ``type=channel.summary`` event with the
        ``conversation_id`` and detected ``pdf_path`` so the channel adapter
        can fire send_file etc.
        """
        await self.start()
        conv = await self.get_active_conversation(db, user, channel=channel)
        prior = await self.recent_messages(db, conv)
        prior_quotes = await self.recent_quotes(db, user)
        body = (
            f"{attachments_block}\n\n{mission_text}".strip()
            if attachments_block else mission_text
        )
        mission = self.build_mission_with_history(prior, body, prior_quotes=prior_quotes)

        await self.append_message(db, conv, role="user", content=mission_text)
        await db.commit()

        pdfs_before = self.snapshot_pdfs()
        agent = await create_maler_agent()
        from src.agents.tools.save_quote_to_db import (
            current_conversation_id,
            current_quote_id,
            current_user_id,
        )
        user_token = current_user_id.set(user.id)
        conv_token = current_conversation_id.set(conv.id)
        quote_token = current_quote_id.set(None)
        pdf_path: Optional[str] = None
        quote_id: Optional[int] = None
        quote_number: Optional[str] = None
        final_message = ""
        status = "completed"
        try:
            async for event in agent.execute_stream(
                mission=mission, session_id=self.session_id_for(conv),
            ):
                etype = (
                    event.event_type.value
                    if hasattr(event.event_type, "value")
                    else str(event.event_type)
                )
                if etype == "tool_result":
                    found = self.extract_pdf_path_from_event(event.data)
                    if found:
                        pdf_path = found
                    qref = self.extract_quote_ref_from_event(event.data)
                    if qref is not None:
                        quote_id, quote_number = qref
                elif etype == "final_answer":
                    final_message = (
                        event.data.get("content")
                        or event.data.get("final_message")
                        or final_message
                    )
                elif etype == "complete":
                    final_message = event.data.get("final_message") or final_message
                elif etype == "error":
                    status = "error"
                yield {"type": etype, "data": event.data}

            if not pdf_path:
                new_pdfs = self.snapshot_pdfs() - pdfs_before
                newest = self.newest_pdf(new_pdfs)
                if newest:
                    pdf_path = str(newest)
        finally:
            try:
                await agent.close()
            except Exception:
                pass
            current_quote_id.reset(quote_token)
            current_conversation_id.reset(conv_token)
            current_user_id.reset(user_token)

        await self.append_message(
            db, conv, role="assistant", content=final_message or "",
            extra_metadata=(
                json.dumps({"pdf_path": pdf_path}, ensure_ascii=False)
                if pdf_path else None
            ),
        )
        await db.commit()

        yield {
            "type": "channel.summary",
            "data": {
                "conversation_id": conv.id,
                "final_message": final_message,
                "pdf_path": pdf_path,
                "quote_id": quote_id,
                "quote_number": quote_number,
                "status": status,
            },
        }


# Module-level singleton — FastAPI lifespan starts it, routes import it.
agent_service = AgentService()
