"""search_materials — pytaskforce ToolProtocol over Pinta's RagService.

Lets the Maler-Agent ground material prices in the (eventually seeded)
MaterialPrice DB instead of guessing "Dispersion ~8 €/L". Returns an empty
list silently when the table is empty so the agent can fall back to its
faustregeln; the system prompt teaches it to use real prices when present.
"""
from __future__ import annotations

from typing import Any

from taskforce.core.interfaces.tools import ApprovalRiskLevel, ToolProtocol


class SearchMaterialsTool(ToolProtocol):
    """Look up material prices in the Pinta knowledge base via RAG."""

    def __init__(self) -> None:
        # Lazy: import here to avoid pulling SQLAlchemy at module import time
        # (keeps the tool importable in tests that don't have a DB).
        pass

    @property
    def name(self) -> str:
        return "search_materials"

    @property
    def description(self) -> str:
        return (
            "Sucht reale Material- und Farbpreise aus der Pinta-Produktdatenbank "
            "(RAG, Cosine-Similarity über Embeddings). Liefert die Top-K relevanten "
            "Treffer für den deutschen Maler-Markt. NUTZE DIES, BEVOR du Materialpreise "
            "schätzt — die zurückgegebenen Werte sind echte Hersteller-Netto-Preise. "
            "Wenn die Datenbank leer ist, kommt eine leere Liste zurück; verwende dann "
            "deine Faustregeln aus dem System-Prompt."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Materialbeschreibung in natürlicher Sprache, z.B. "
                        "'Dispersionsfarbe weiß Allergiker' oder 'Silikatfarbe Fassade Cremegelb'."
                    ),
                },
                "region": {
                    "type": "string",
                    "description": (
                        "Optional: PLZ-Präfix oder Region-Tag, z.B. 'DE', 'DE-1'. "
                        "Wird genutzt, um regionale Preise zu bevorzugen."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": "Anzahl der zurückgegebenen Treffer (default 5, max 10).",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def approval_risk_level(self) -> ApprovalRiskLevel:
        return ApprovalRiskLevel.LOW

    async def execute(
        self,
        query: str,
        region: str | None = None,
        top_k: int = 5,
        **_ignored: Any,
    ) -> dict[str, Any]:
        # Local imports keep the heavy deps (sqlalchemy, openai) lazy
        from sqlalchemy import inspect as sa_inspect
        from src.core.database import AsyncSessionLocal, engine
        from src.services.ai_service import AIService
        from src.services.rag_service import RagService

        # Pre-check: if the material_prices table does not exist (DB never
        # seeded), short-circuit with a friendly success+empty rather than
        # let SQLAlchemy raise an OperationalError on every call. The agent
        # would otherwise stall in repeated retries, which trips the Azure
        # content filter and burns tokens for nothing.
        try:
            def _check(sync_conn) -> bool:
                return sa_inspect(sync_conn).has_table("material_prices")
            async with engine.begin() as conn:
                table_exists = await conn.run_sync(_check)
            if not table_exists:
                return {
                    "success": True,
                    "count": 0,
                    "materials": [],
                    "note": (
                        "Materialdatenbank ist noch nicht initialisiert "
                        "(material_prices-Tabelle fehlt). Nutze die Faustregeln "
                        "aus dem System-Prompt — KEIN weiteres search_materials "
                        "in dieser Mission aufrufen."
                    ),
                }
        except Exception as exc:
            return {
                "success": True,
                "count": 0,
                "materials": [],
                "note": (
                    f"Materialdatenbank nicht erreichbar ({type(exc).__name__}). "
                    "Nutze Faustregeln und ruf das Tool nicht erneut auf."
                ),
            }

        try:
            top_k = max(1, min(int(top_k or 5), 10))
            rag = RagService(ai_service=AIService())
            async with AsyncSessionLocal() as db:
                materials = await rag.retrieve_materials(
                    db=db, query=query, region=region, top_k=top_k
                )
            results = RagService.materials_to_prompt_context(materials)
            return {
                "success": True,
                "count": len(results),
                "materials": results,
                "note": (
                    "Datenbank ist leer — Faustregeln aus System-Prompt verwenden."
                    if not results
                    else f"{len(results)} Treffer gefunden (Region={region or 'beliebig'})."
                ),
            }
        except Exception as exc:  # pragma: no cover — surfaced to the agent
            return {
                "success": True,  # don't propagate as failure -> avoids stall
                "count": 0,
                "materials": [],
                "note": (
                    f"search_materials hatte einen Fehler ({type(exc).__name__}). "
                    "Ich nutze stattdessen Faustregeln und rufe das Tool nicht erneut auf."
                ),
            }
