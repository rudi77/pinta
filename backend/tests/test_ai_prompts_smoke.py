"""Regression tests guarding against the f-string-in-system-prompt bug.

History: an earlier version of `ai_service.py` embedded a raw JSON example
inside an f-string, so Python interpreted the literal `{` characters as
format-spec markers. Building the prompt raised `ValueError: Invalid format
specifier ...`, the broad `except Exception` swallowed it, and every
generation call silently returned static mock data. The bug was invisible in
production until strict mode was added.

These tests build the prompts via the real code path with a stubbed OpenAI
client, so any reintroduction of unescaped `{` inside an f-string fails
loudly — without consuming OpenAI tokens.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("AI_STRICT_MODE", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-test_dummy_key_for_smoke_only")

from src.services.ai_service import AIService  # noqa: E402


def _stub_openai_response(payload: dict) -> MagicMock:
    """Build a fake OpenAI ChatCompletion response wrapping `payload` as JSON."""
    msg = MagicMock()
    msg.content = json.dumps(payload, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_service_with_stub(stub_payload: dict) -> AIService:
    service = AIService()
    # Force enabled even if the env-var trick didn't take (e.g. cached Settings)
    service.enabled = True
    if service.client is None:
        service.client = MagicMock()
        service.model = "gpt-4o-mini"
        service.vision_model = "gpt-4o"
        service.embedding_model = "text-embedding-3-small"
    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(
        return_value=_stub_openai_response(stub_payload)
    )
    return service


def test_quick_quote_prompt_builds_without_fstring_crash():
    """Regression: generate_quick_quote must not raise ValueError from the prompt."""
    payload = {
        "project_title": "Test",
        "items": [
            {"position": 1, "description": "x", "quantity": 1.0, "unit": "m²",
             "unit_price": 1.0, "total_price": 1.0, "category": "labor"}
        ],
        "subtotal": 1.0, "vat_amount": 0.19, "total_amount": 1.19,
        "notes": "", "recommendations": []
    }
    service = _make_service_with_stub(payload)

    result = asyncio.run(service.generate_quick_quote(
        service_description="2 Wände in 12m² streichen",
        area="12 m²",
        additional_info=None,
        hourly_rate=50.0,
        material_cost_markup=15.0,
    ))

    assert result == payload, "Prompt built and stub response was returned"
    # Verify the system prompt actually went out and contains the JSON schema
    sent_messages = service.client.chat.completions.create.call_args.kwargs["messages"]
    system_prompt = sent_messages[0]["content"]
    assert "JSON-Format" in system_prompt
    # JSON example in prompt must contain literal { } (proves the f-string
    # double-brace escape produced real braces in the final string)
    assert '"project_title"' in system_prompt
    assert '"items"' in system_prompt
    # Cost params must be substituted
    assert "50.00 EUR/h" in system_prompt
    assert "15.0%" in system_prompt


def test_quote_generation_prompt_builds_without_fstring_crash():
    """Regression: process_answers_and_generate_quote prompt must not crash."""
    payload = {
        "quote": {"project_title": "Test", "total_amount": 100.0,
                  "labor_hours": 2.0, "hourly_rate": 50.0,
                  "material_cost": 0.0, "additional_costs": 0.0},
        "items": [{"description": "x", "quantity": 1.0, "unit": "Stk",
                   "unit_price": 100.0, "total_price": 100.0,
                   "category": "labor"}],
        "notes": "", "recommendations": []
    }
    service = _make_service_with_stub(payload)

    result = asyncio.run(service.process_answers_and_generate_quote(
        project_data={"description": "Test", "area": "12 m²"},
        answers=[{"question_id": "x", "answer": "y"}],
        conversation_history=None,
        document_files=None,
        hourly_rate=55.0,
        material_cost_markup=20.0,
        material_context=None,
    ))

    assert result == payload
    sent_messages = service.client.chat.completions.create.call_args.kwargs["messages"]
    system_prompt = sent_messages[0]["content"]
    assert '"quote"' in system_prompt
    assert '"items"' in system_prompt
    assert "55.00 EUR/h" in system_prompt
    assert "20.0%" in system_prompt


def test_quote_generation_with_material_context_inlined():
    """RAG context must be embedded into the prompt without breaking it."""
    payload = {"quote": {"project_title": "T", "total_amount": 0.0,
                         "labor_hours": 0.0, "hourly_rate": 0.0,
                         "material_cost": 0.0, "additional_costs": 0.0},
               "items": [], "notes": "", "recommendations": []}
    service = _make_service_with_stub(payload)

    material_context = [
        {"name": "Alpina Weiss", "manufacturer": "Alpina", "unit": "L",
         "price_net": 4.99, "region": "DE"},
        {"name": "Tiefgrund", "manufacturer": "Knauf", "unit": "L",
         "price_net": 3.50, "region": "DE-1"},
    ]
    asyncio.run(service.process_answers_and_generate_quote(
        project_data={"description": "Test"}, answers=[],
        material_context=material_context,
    ))

    sent_messages = service.client.chat.completions.create.call_args.kwargs["messages"]
    system_prompt = sent_messages[0]["content"]
    assert "REALE MATERIALPREISE" in system_prompt
    assert "Alpina Weiss" in system_prompt
    assert "4.99 EUR/L" in system_prompt
