"""Conversation state per Telegram chat.

MVP-Variante: 1 Session = 1 aktiver Draft pro ``chat_id``.
``/neu`` wipet die Session. Multi-Draft-Switching kommt später (cheap refactor).

Persistenz: aktuell in-memory. Sobald der Bot im Cluster läuft oder Neustarts
häufig sind, auf Redis oder Postgres (`quote_drafts`-Tabelle) migrieren.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ChatSession:
    chat_id: int
    user_id: Optional[int] = None          # Pinta user, gefüllt nach /start linking
    active_draft_id: Optional[int] = None  # FK auf quote_drafts.id, sobald persistiert
    history: List[dict] = field(default_factory=list)


_sessions: Dict[int, ChatSession] = {}


def get_session_for_chat(chat_id: int) -> ChatSession:
    if chat_id not in _sessions:
        _sessions[chat_id] = ChatSession(chat_id=chat_id)
    return _sessions[chat_id]


def reset_session_for_chat(chat_id: int) -> ChatSession:
    _sessions[chat_id] = ChatSession(chat_id=chat_id)
    return _sessions[chat_id]
