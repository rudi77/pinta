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
        from src.core.database import AsyncSessionLocal
        from src.services.ai_service import AIService
        from src.services.rag_service import RagService

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
                "success": False,
                "error": f"search_materials failed: {type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
                "materials": [],
                "count": 0,
            }
