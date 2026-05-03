"""save_quote_to_db — persists the agent's finished quote into the Pinta DB.

This is the bridge between the pytaskforce agent and the central Quote /
QuoteItem tables. The same quote that ends up as a PDF for Telegram should
ALSO appear in the Web Dashboard and respect the quota machinery.

We pull the active user from the agent factory's per-mission context
(set by AgentService before each ``execute_stream``). For now: the agent
calls this tool with the quote dict, we look up the user by id from a
context-local variable, and INSERT one Quote row + N QuoteItem rows.

Returns ``{success: True, quote_id, quote_number}`` so the agent can
mention the quote_number to the user ("Voranschlag KV-…-abc fertig.").
"""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from taskforce.core.interfaces.tools import ApprovalRiskLevel, ToolProtocol

logger = logging.getLogger(__name__)


# Set by AgentService.chat()/chat_stream() before invoking the agent so the
# tool knows which user owns the resulting quote. ContextVar = task-local,
# safe under concurrent missions.
current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)
current_conversation_id: ContextVar[Optional[int]] = ContextVar(
    "current_conversation_id", default=None,
)


def _generate_quote_number() -> str:
    return f"KV-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"


class SaveQuoteToDbTool(ToolProtocol):
    """Persist the agent's final quote into the Pinta `quotes` table."""

    @property
    def name(self) -> str:
        return "save_quote_to_db"

    @property
    def description(self) -> str:
        return (
            "Speichert den fertigen Kostenvoranschlag in der zentralen "
            "Pinta-Datenbank, sodass er auch im Web-Dashboard sichtbar ist. "
            "RUFE DIESES TOOL AUF, sobald das Quote-Dict komplett ist UND "
            "BEVOR du generate_quote_pdf aufrufst — dann landen Quote "
            "(mit quote_number), Items, Customer-Felder konsistent in der DB. "
            "Liefert die quote_number zurück, die du dem Nutzer mitteilen "
            "kannst."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "quote": {
                    "type": "object",
                    "description": (
                        "Komplettes Quote-Dict: project_title (Pflicht), items "
                        "(Liste mit description/quantity/unit/unit_price/total_price/category), "
                        "subtotal, vat_amount, total_amount, notes, recommendations, "
                        "optional: customer_name, customer_email, customer_phone, "
                        "customer_address, project_description."
                    ),
                },
            },
            "required": ["quote"],
        }

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def approval_risk_level(self) -> ApprovalRiskLevel:
        return ApprovalRiskLevel.LOW

    async def execute(
        self, quote: dict[str, Any] | None = None, **_ignored: Any,
    ) -> dict[str, Any]:
        if not isinstance(quote, dict) or not quote:
            return {
                "success": False,
                "error": "quote-Argument fehlt oder ist kein dict.",
                "error_type": "MissingArgument",
            }

        user_id = current_user_id.get()
        if user_id is None:
            return {
                "success": False,
                "error": (
                    "Kein User-Kontext aktiv. save_quote_to_db kann nur "
                    "im Rahmen einer AgentService-Mission aufgerufen werden."
                ),
                "error_type": "NoUserContext",
            }

        # Lazy DB import — keeps Tool importable in unit tests
        from src.core.database import AsyncSessionLocal
        from src.models.models import Quote, QuoteItem

        try:
            quote_number = _generate_quote_number()
            items = quote.get("items") or []

            async with AsyncSessionLocal() as db:
                row = Quote(
                    quote_number=quote_number,
                    user_id=user_id,
                    customer_name=str(quote.get("customer_name") or "—"),
                    customer_email=quote.get("customer_email"),
                    customer_phone=quote.get("customer_phone"),
                    customer_address=quote.get("customer_address"),
                    project_title=str(quote.get("project_title") or "Kostenvoranschlag"),
                    project_description=quote.get("project_description")
                    or quote.get("notes"),
                    total_amount=float(quote.get("total_amount") or 0),
                    labor_hours=float(quote.get("labor_hours") or 0),
                    hourly_rate=float(quote.get("hourly_rate") or 0),
                    material_cost=float(quote.get("material_cost") or 0),
                    additional_costs=float(quote.get("additional_costs") or 0),
                    status="draft",
                    ai_processing_status="completed",
                    created_by_ai=True,
                    generation_method="agent",
                    conversation_history=(
                        json.dumps(
                            {"conversation_id": current_conversation_id.get()},
                            ensure_ascii=False,
                        )
                        if current_conversation_id.get() is not None
                        else None
                    ),
                )
                db.add(row)
                await db.flush()

                for idx, item in enumerate(items, start=1):
                    try:
                        qty = float(item.get("quantity") or 0)
                        unit_price = float(item.get("unit_price") or 0)
                        total_price = float(
                            item.get("total_price") or qty * unit_price
                        )
                    except (TypeError, ValueError):
                        qty, unit_price, total_price = 0.0, 0.0, 0.0
                    db.add(QuoteItem(
                        quote_id=row.id,
                        position=int(item.get("position") or idx),
                        description=str(item.get("description") or ""),
                        quantity=qty,
                        unit=str(item.get("unit") or "Stk"),
                        unit_price=unit_price,
                        total_price=total_price,
                        room_name=item.get("room_name"),
                        area_sqm=item.get("area_sqm"),
                        work_type=item.get("category") or item.get("work_type"),
                    ))

                await db.commit()
                quote_id = row.id

            logger.info(
                "save_quote_to_db.persisted user=%s quote_id=%s number=%s items=%s",
                user_id, quote_id, quote_number, len(items),
            )
            return {
                "success": True,
                "quote_id": quote_id,
                "quote_number": quote_number,
                "user_id": user_id,
                "items_count": len(items),
                "note": (
                    f"Quote {quote_number} ist in der Pinta-DB gespeichert "
                    "und im Web-Dashboard sichtbar."
                ),
            }
        except Exception as exc:
            logger.exception("save_quote_to_db failed")
            return {
                "success": False,
                "error": f"DB-Persistierung fehlgeschlagen: {type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
            }
