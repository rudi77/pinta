"""Per-chat conversation memory for the Pinta Maler-Agent.

We're running pytaskforce in **library mode** — that means we deliberately
skip the heavy ``PersistentAgentService`` / ``ConversationManager`` orches-
tration and do the chat memory ourselves. ``LeanAgent.execute_stream`` does
not accept a prior-messages parameter; its internal ``MessageHistoryManager``
loads from the ``StateManager``, which only carries the planner state, not
the chat transcript.

So: we keep a small JSON log per Telegram chat under
``backend/.taskforce_maler/conversations/<chat_id>.json`` and inject the
recent turns as a prefix in the next mission string. The agent then "sees"
the last N exchanges as context and stops claiming amnesia between
follow-up questions.

When the user sends ``/neu`` the log is wiped — that's the explicit
session-reset contract.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

_CONV_DIR = (
    Path(__file__).resolve().parents[2] / ".taskforce_maler" / "conversations"
)
_LOCK = threading.Lock()
_MAX_TURNS_KEEP = 30          # hard cap per chat (older turns get pruned)
_MAX_TURNS_PREFIX = 8         # how many recent turns we splice into the mission
_MAX_CONTENT_CHARS = 1500     # truncate verbose assistant replies in the prefix


def _path_for(chat_id: str | int) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", str(chat_id))
    return _CONV_DIR / f"{safe}.json"


def _load(chat_id: str | int) -> list[dict]:
    p = _path_for(chat_id)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("conversation_log.load_failed chat=%s err=%s", chat_id, exc)
    return []


def _save(chat_id: str | int, turns: list[dict]) -> None:
    p = _path_for(chat_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(turns, f, ensure_ascii=False, indent=2)
        tmp.replace(p)
    except OSError as exc:
        logger.warning("conversation_log.save_failed chat=%s err=%s", chat_id, exc)


def append(chat_id: str | int, role: str, content: str) -> None:
    """Append one turn to the chat log (thread-safe-enough for our scale)."""
    if not content:
        return
    with _LOCK:
        turns = _load(chat_id)
        turns.append({"role": role, "content": content, "ts": int(time.time())})
        if len(turns) > _MAX_TURNS_KEEP:
            turns = turns[-_MAX_TURNS_KEEP:]
        _save(chat_id, turns)


def clear(chat_id: str | int) -> None:
    """Wipe the chat log (used by ``/neu`` and friends)."""
    p = _path_for(chat_id)
    with _LOCK:
        if p.exists():
            try:
                p.unlink()
            except OSError as exc:
                logger.warning("conversation_log.clear_failed chat=%s err=%s", chat_id, exc)


def recent_turns(chat_id: str | int, limit: int = _MAX_TURNS_PREFIX) -> list[dict]:
    with _LOCK:
        turns = _load(chat_id)
    return turns[-limit:]


def build_mission_with_history(chat_id: str | int, new_user_text: str) -> str:
    """Wrap the new user message with a compact transcript of prior turns.

    Format is plain Markdown so the agent reads it as natural context, not
    as something to parrot back. We deliberately keep the prefix short — the
    agent's internal context tokens are precious and we already pay for the
    system prompt + tool schemas.
    """
    history = recent_turns(chat_id, limit=_MAX_TURNS_PREFIX)
    if not history:
        return new_user_text

    lines = [
        "Bisheriger Chat-Verlauf (älteste zuerst, gekürzt):",
    ]
    for turn in history:
        role = "Nutzer" if turn.get("role") == "user" else "Du"
        content = (turn.get("content") or "").strip()
        if len(content) > _MAX_CONTENT_CHARS:
            content = content[: _MAX_CONTENT_CHARS - 1] + "…"
        lines.append(f"- **{role}:** {content}")

    lines.append("")
    lines.append("Aktuelle Nachricht des Nutzers:")
    lines.append(new_user_text)
    return "\n".join(lines)


def known_chats() -> Iterable[str]:
    """Diagnostic helper — list chat ids we have a log for."""
    if not _CONV_DIR.exists():
        return []
    return [p.stem for p in _CONV_DIR.glob("*.json")]
