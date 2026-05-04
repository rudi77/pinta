"""Unified agent endpoint — both the Web App and the Telegram-Bot adapter
talk to this. Replaces the per-channel agent wiring we had before.

Endpoints:
  POST /api/v1/agent/chat            sync, returns final reply + pdf hint
  POST /api/v1/agent/chat/stream     SSE stream (llm_token + summary)
  GET  /api/v1/agent/conversations   user's conversation list
  GET  /api/v1/agent/conversations/{id}/messages
  POST /api/v1/agent/reset           archive active conversation
  GET  /api/v1/agent/pdf/{name}      download a generated quote PDF

Bot adapter sub-namespace (auth = X-Bot-Service-Token + X-Channel /
X-External-Id headers, NOT user JWT):
  POST /api/v1/agent/bot/chat        chat through bot, auto-creates shadow user
  POST /api/v1/agent/bot/reset       /neu over bot
  POST /api/v1/agent/bot/link        consume a linking_token issued by the Web
  POST /api/v1/agent/linking-token   user-side: issue a token to paste into bot
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.tools.save_quote_to_db import (
    current_conversation_id,
    current_user_id,
)
from src.core.database import get_db
from src.core.security import get_current_user
from src.core.settings import settings
from src.models.models import ChannelLink, Conversation, ConversationMessage, User
from src.services.agent_service import agent_service
from src.services.channel_link_service import (
    consume_linking_token,
    issue_linking_token,
    resolve_or_create_shadow_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

_QUOTES_DIR = (
    Path(__file__).resolve().parents[2] / ".taskforce_maler" / "quotes"
)


# ── request / response schemas ────────────────────────────────────────────

class AgentAttachment(BaseModel):
    """Inline attachment description handed to the agent.

    For Web uploads this is a server-side file_path the agent can read.
    For Telegram, the bot adapter constructs the same shape.
    """
    file_path: str
    file_name: Optional[str] = None
    type: str = Field(default="file", description="image | document | file")


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    attachments: list[AgentAttachment] = Field(default_factory=list)
    channel: str = Field(default="web", pattern="^(web|telegram|api)$")


class AgentChatResponse(BaseModel):
    conversation_id: int
    final_message: str
    humanized_message: str  # cleaned-of-JSON version safe for chat UIs
    pdf_url: Optional[str] = None
    pdf_filename: Optional[str] = None
    quote_id: Optional[int] = None
    quote_number: Optional[str] = None
    status: str


class ConversationListEntry(BaseModel):
    id: int
    channel: str
    title: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    message_count: int


class ConversationMessageEntry(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    extra_metadata: Optional[dict[str, Any]] = None


# ── helpers ───────────────────────────────────────────────────────────────

def _build_attachments_block(attachments: list[AgentAttachment]) -> str:
    if not attachments:
        return ""
    lines = [
        "Der Nutzer hat folgende Datei(en) mitgeschickt — lies sie mit dem "
        "`multimedia`-Tool ein, bevor du antwortest:",
    ]
    for att in attachments:
        kind = att.type or "file"
        name = att.file_name or "datei"
        lines.append(f"- {kind}: `{att.file_path}` (Dateiname: {name})")
    return "\n".join(lines)


def _humanize(raw: str) -> str:
    """Strip raw JSON / code fences and give the chat UI a clean summary.

    Mirror of the Telegram runner's _humanize_reply but kept here so the
    Web channel doesn't depend on the bot module.
    """
    if not raw or not raw.strip():
        return raw or ""
    text = raw.strip()

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

    cleaned = re.sub(r"```[\s\S]*?```", "", text).strip()
    cleaned = re.sub(
        r"^\s*\{[\s\S]*?\}\s*$", "", cleaned, flags=re.MULTILINE,
    ).strip()

    if quote:
        title = quote.get("project_title") or "Kostenvoranschlag"
        sub = quote.get("subtotal")
        vat = quote.get("vat_amount")
        total = quote.get("total_amount")

        def _fmt(v: Any) -> str:
            try:
                return (
                    f"{float(v):,.2f}"
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
            except (TypeError, ValueError):
                return "—"

        out = [title]
        if sub is not None and vat is not None and total is not None:
            out.append(
                f"Netto: {_fmt(sub)} EUR · MwSt 19%: {_fmt(vat)} EUR · "
                f"Brutto: {_fmt(total)} EUR"
            )
        notes = (quote.get("notes") or "").strip()
        if notes:
            short = notes.split(".")[0].strip()
            if short:
                out.append(short + ".")
        out.append("📄 PDF kommt gleich als Download.")
        if cleaned and "{" not in cleaned and "}" not in cleaned and len(cleaned) < 600:
            return cleaned + "\n\n" + "\n".join(out)
        return "\n".join(out)

    return cleaned or raw


def _pdf_response_fields(pdf_path: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not pdf_path:
        return None, None
    name = Path(pdf_path).name
    return f"/api/v1/agent/pdf/{name}", name


def _quote_number_from_message(content: str) -> Optional[str]:
    """Spot-check the assistant text for a generated KV-… number."""
    m = re.search(r"\bKV-\d{8}-\d{6}-[a-f0-9]{6}\b", content)
    return m.group(0) if m else None


# ── routes ────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentChatResponse:
    """One-shot chat: run mission, return final reply and (if any) PDF link."""
    attachments_block = _build_attachments_block(request.attachments)

    # ContextVars so save_quote_to_db knows whose quote it belongs to.
    user_token = current_user_id.set(user.id)
    conv_token = current_conversation_id.set(None)
    try:
        result = await agent_service.chat(
            db, user, request.message,
            channel=request.channel,
            attachments_block=attachments_block,
        )
        # Re-bind the conversation id once we know it (so any sub-tool that
        # reads current_conversation_id later in the same task picks it up).
        current_conversation_id.set(result["conversation_id"])
    finally:
        current_user_id.reset(user_token)
        current_conversation_id.reset(conv_token)

    pdf_url, pdf_filename = _pdf_response_fields(result.get("pdf_path"))
    return AgentChatResponse(
        conversation_id=result["conversation_id"],
        final_message=result.get("final_message", ""),
        humanized_message=_humanize(result.get("final_message", "")),
        pdf_url=pdf_url,
        pdf_filename=pdf_filename,
        quote_id=result.get("quote_id"),
        quote_number=(
            result.get("quote_number")
            or _quote_number_from_message(result.get("final_message", ""))
        ),
        status=result.get("status", "completed"),
    )


@router.post("/chat/stream")
async def agent_chat_stream(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Server-Sent Events stream of agent events.

    Each event line is ``data: <json>\\n\\n``. Final event has type
    ``channel.summary`` with conversation_id and pdf_url.
    """
    attachments_block = _build_attachments_block(request.attachments)

    async def _gen():
        user_token = current_user_id.set(user.id)
        conv_token = current_conversation_id.set(None)
        try:
            async for event in agent_service.chat_stream(
                db, user, request.message,
                channel=request.channel,
                attachments_block=attachments_block,
            ):
                if event.get("type") == "channel.summary":
                    pdf_url, pdf_filename = _pdf_response_fields(
                        event["data"].get("pdf_path")
                    )
                    event["data"]["pdf_url"] = pdf_url
                    event["data"]["pdf_filename"] = pdf_filename
                    event["data"]["humanized_message"] = _humanize(
                        event["data"].get("final_message", "")
                    )
                    current_conversation_id.set(event["data"].get("conversation_id"))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            current_user_id.reset(user_token)
            current_conversation_id.reset(conv_token)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationListEntry])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    out = []
    for c in rows:
        # cheap message count — a full COUNT subquery would be cleaner once
        # we hit perf issues, but per-user volumes are tiny.
        msg_count = len(
            (await db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == c.id)
            )).scalars().all()
        )
        out.append(ConversationListEntry(
            id=c.id, channel=c.channel, title=c.title,
            is_active=c.is_active,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else "",
            message_count=msg_count,
        ))
    return out


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageEntry],
)
async def conversation_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    rows = (await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.id)
    )).scalars().all()
    return [
        ConversationMessageEntry(
            id=m.id, role=m.role, content=m.content,
            created_at=m.created_at.isoformat() if m.created_at else "",
            extra_metadata=(
                json.loads(m.extra_metadata) if m.extra_metadata else None
            ),
        )
        for m in rows
    ]


@router.post("/reset")
async def reset_conversation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    channel: str = "web",
) -> dict[str, Any]:
    fresh = await agent_service.reset(db, user, channel=channel)
    return {
        "success": True,
        "new_conversation_id": fresh.id,
        "channel": fresh.channel,
    }


# ── bot adapter sub-namespace ────────────────────────────────────────────

class BotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    attachments: list[AgentAttachment] = Field(default_factory=list)
    display_name: Optional[str] = None


class BotLinkRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=64)
    display_name: Optional[str] = None


async def get_bot_user(
    x_bot_service_token: str = Header(..., alias="X-Bot-Service-Token"),
    x_channel: str = Header(..., alias="X-Channel"),
    x_external_id: str = Header(..., alias="X-External-Id"),
    x_display_name: Optional[str] = Header(default=None, alias="X-Display-Name"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Auth dependency for bot adapter calls.

    Verifies the shared bot-service token, then resolves
    ``(channel, external_id)`` to a Pinta user. Auto-creates a shadow user
    on first encounter so the bot can start chatting immediately; the user
    can later upgrade via ``/api/v1/agent/bot/link``.
    """
    expected = (settings.bot_service_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Bot service token not configured on the backend.",
        )
    if not x_bot_service_token or x_bot_service_token != expected:
        raise HTTPException(status_code=401, detail="Invalid bot service token.")
    if not x_channel or not x_external_id:
        raise HTTPException(
            status_code=400,
            detail="X-Channel and X-External-Id headers are required.",
        )
    user, _link, _created = await resolve_or_create_shadow_user(
        db,
        channel=x_channel.strip().lower(),
        external_id=x_external_id.strip(),
        display_name=x_display_name.strip() if x_display_name else None,
    )
    return user


@router.post("/bot/chat", response_model=AgentChatResponse)
async def bot_chat(
    request: BotChatRequest,
    x_channel: str = Header(..., alias="X-Channel"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_bot_user),
) -> AgentChatResponse:
    attachments_block = _build_attachments_block(request.attachments)
    user_token = current_user_id.set(user.id)
    conv_token = current_conversation_id.set(None)
    try:
        result = await agent_service.chat(
            db, user, request.message,
            channel=x_channel.strip().lower(),
            attachments_block=attachments_block,
        )
        current_conversation_id.set(result["conversation_id"])
    finally:
        current_user_id.reset(user_token)
        current_conversation_id.reset(conv_token)

    pdf_url, pdf_filename = _pdf_response_fields(result.get("pdf_path"))
    return AgentChatResponse(
        conversation_id=result["conversation_id"],
        final_message=result.get("final_message", ""),
        humanized_message=_humanize(result.get("final_message", "")),
        pdf_url=pdf_url,
        pdf_filename=pdf_filename,
        quote_id=result.get("quote_id"),
        quote_number=(
            result.get("quote_number")
            or _quote_number_from_message(result.get("final_message", ""))
        ),
        status=result.get("status", "completed"),
    )


@router.post("/bot/reset")
async def bot_reset(
    x_channel: str = Header(..., alias="X-Channel"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_bot_user),
) -> dict[str, Any]:
    fresh = await agent_service.reset(db, user, channel=x_channel.strip().lower())
    return {"success": True, "new_conversation_id": fresh.id}


@router.post("/bot/link")
async def bot_link(
    request: BotLinkRequest,
    x_channel: str = Header(..., alias="X-Channel"),
    x_external_id: str = Header(..., alias="X-External-Id"),
    x_bot_service_token: str = Header(..., alias="X-Bot-Service-Token"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Link a bot channel identity to a real Pinta user via a one-shot token."""
    expected = (settings.bot_service_token or "").strip()
    if not expected or x_bot_service_token != expected:
        raise HTTPException(status_code=401, detail="Invalid bot service token.")

    real_user = await consume_linking_token(
        db,
        token=request.token,
        channel=x_channel.strip().lower(),
        external_id=x_external_id.strip(),
        display_name=request.display_name,
    )
    if real_user is None:
        return {
            "success": False,
            "error": "Token unbekannt oder abgelaufen.",
        }
    return {
        "success": True,
        "user_id": real_user.id,
        "username": real_user.username,
    }


@router.post("/linking-token")
async def issue_linking_token_endpoint(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    channel: str = "telegram",
) -> dict[str, Any]:
    """Web-side: issue a token the user pastes into Telegram.

    TTL is configurable via ``settings.linking_token_ttl_hours`` (default
    30 days). Response also carries the bot username so the frontend can
    build a deep-link the user only has to click once.
    """
    token, expires = await issue_linking_token(db, user, channel=channel)
    bot_username = (settings.telegram_bot_username or "").strip().lstrip("@")
    deep_link = (
        f"https://t.me/{bot_username}?start={token}" if bot_username else None
    )
    return {
        "token": token,
        "expires_at": expires.isoformat(),
        "channel": channel,
        "bot_username": bot_username or None,
        "deep_link": deep_link,
        "command": f"/link {token}",
    }


@router.get("/channel-links")
async def list_channel_links(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the user's confirmed channel links + bot config for the UI.

    Filters out token placeholders (``external_id`` starts with
    ``pending-``) so callers only see actually-paired chats.
    """
    rows = (await db.execute(
        select(ChannelLink)
        .where(ChannelLink.user_id == user.id)
        .order_by(ChannelLink.id.desc())
    )).scalars().all()

    links: list[dict[str, Any]] = []
    for row in rows:
        if (row.external_id or "").startswith("pending-"):
            continue
        links.append({
            "id": row.id,
            "channel": row.channel,
            "external_id": row.external_id,
            "display_name": row.display_name,
            "is_anonymous_shadow": bool(row.is_anonymous_shadow),
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        })

    bot_username = (settings.telegram_bot_username or "").strip().lstrip("@")
    return {
        "links": links,
        "bot_username": bot_username or None,
        "linking_token_ttl_hours": int(settings.linking_token_ttl_hours or 0),
    }


@router.get("/pdf/{name}")
async def download_quote_pdf(
    name: str,
    user: User = Depends(get_current_user),  # auth gate; pdf names are slugs
):
    # Path-traversal defence — only files inside _QUOTES_DIR are allowed.
    safe_name = Path(name).name
    candidate = (_QUOTES_DIR / safe_name).resolve()
    if not str(candidate).startswith(str(_QUOTES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path.")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(
        path=str(candidate),
        media_type="application/pdf",
        filename=safe_name,
    )
