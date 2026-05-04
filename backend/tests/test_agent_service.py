"""Unit tests for agent_service helpers (P4 splice + extractors)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.services.agent_service import AgentService


def _msg(role: str, content: str):
    return SimpleNamespace(role=role, content=content)


def _quote(quote_number: str, project_title: str, customer_name: str, total: float):
    return SimpleNamespace(
        quote_number=quote_number,
        project_title=project_title,
        customer_name=customer_name,
        total_amount=total,
        created_at=datetime(2026, 5, 4, 10, 0, 0),
    )


def test_build_mission_no_history_returns_input_unchanged():
    out = AgentService.build_mission_with_history([], "Hallo")
    assert out == "Hallo"


def test_build_mission_with_only_messages():
    msgs = [_msg("user", "Wand 25qm"), _msg("assistant", "OK, Latex?")]
    out = AgentService.build_mission_with_history(msgs, "weiß")
    assert "Bisheriger Chat-Verlauf" in out
    assert "Wand 25qm" in out
    assert "Aktuelle Nachricht des Nutzers:" in out
    assert "weiß" in out


def test_build_mission_with_only_quotes():
    quotes = [_quote("KV-001", "Wohnzimmer", "Schmidt", 1234.5)]
    out = AgentService.build_mission_with_history(
        [], "Neuer Auftrag", prior_quotes=quotes,
    )
    assert "Letzte Angebote dieses Nutzers" in out
    assert "KV-001" in out
    assert "Wohnzimmer" in out
    assert "Schmidt" in out
    assert "1234.50" in out
    assert "Aktuelle Nachricht des Nutzers:" in out


def test_build_mission_with_messages_and_quotes_orders_quotes_first():
    msgs = [_msg("user", "x")]
    quotes = [_quote("KV-A", "Bad", "Müller", 999.0)]
    out = AgentService.build_mission_with_history(
        msgs, "go", prior_quotes=quotes,
    )
    quote_idx = out.index("Letzte Angebote dieses Nutzers")
    msg_idx = out.index("Bisheriger Chat-Verlauf")
    assert quote_idx < msg_idx


def test_build_mission_truncates_long_messages():
    long = "A" * 2000
    msgs = [_msg("user", long)]
    out = AgentService.build_mission_with_history(msgs, "next")
    assert "…" in out


def test_extract_pdf_path_finds_nested_success_dict():
    event = {
        "tool_call_id": "x",
        "result": {
            "success": True,
            "file_path": "/tmp/.taskforce_maler/quotes/foo.pdf",
            "size_bytes": 12345,
        },
    }
    assert AgentService.extract_pdf_path_from_event(event) == \
        "/tmp/.taskforce_maler/quotes/foo.pdf"


def test_extract_pdf_path_ignores_failure_dict():
    event = {"result": {"success": False, "file_path": "x.pdf"}}
    assert AgentService.extract_pdf_path_from_event(event) is None


def test_extract_pdf_path_ignores_non_pdf_files():
    event = {"result": {"success": True, "file_path": "/tmp/foo.txt"}}
    assert AgentService.extract_pdf_path_from_event(event) is None


def test_extract_quote_ref_returns_id_and_number():
    event = {
        "result": {
            "success": True,
            "quote_id": 42,
            "quote_number": "KV-20260504-abc",
        },
    }
    assert AgentService.extract_quote_ref_from_event(event) == (42, "KV-20260504-abc")


def test_extract_quote_ref_returns_none_when_missing():
    assert AgentService.extract_quote_ref_from_event({"foo": "bar"}) is None


def test_session_id_for_is_stable_per_conversation():
    conv = SimpleNamespace(id=7)
    assert AgentService.session_id_for(conv) == "pinta-conv-7"


@pytest.mark.asyncio
async def test_recent_quotes_returns_user_quotes_newest_first(test_session, test_user):
    from src.models.models import Quote

    for i in range(3):
        q = Quote(
            quote_number=f"KV-{i:03d}",
            user_id=test_user.id,
            customer_name=f"Kunde {i}",
            project_title=f"Projekt {i}",
            total_amount=100.0 * (i + 1),
        )
        test_session.add(q)
    await test_session.commit()

    service = AgentService()
    rows = await service.recent_quotes(test_session, test_user, limit=2)

    assert len(rows) == 2
    # Newest first (highest id)
    assert rows[0].quote_number == "KV-002"
    assert rows[1].quote_number == "KV-001"


@pytest.mark.asyncio
async def test_recent_quotes_does_not_leak_other_users(test_session, test_user):
    from src.core.security import get_password_hash
    from src.models.models import Quote, User
    import uuid

    other = User(
        email=f"other-{uuid.uuid4().hex[:6]}@example.com",
        username=f"other-{uuid.uuid4().hex[:6]}",
        hashed_password=get_password_hash("xx"),
        is_active=True,
    )
    test_session.add(other)
    await test_session.commit()
    await test_session.refresh(other)

    test_session.add_all([
        Quote(
            quote_number="OTHER-1",
            user_id=other.id,
            customer_name="x",
            project_title="t",
            total_amount=1,
        ),
        Quote(
            quote_number="MINE-1",
            user_id=test_user.id,
            customer_name="x",
            project_title="t",
            total_amount=1,
        ),
    ])
    await test_session.commit()

    service = AgentService()
    rows = await service.recent_quotes(test_session, test_user)
    assert {q.quote_number for q in rows} == {"MINE-1"}
