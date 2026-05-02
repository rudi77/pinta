"""Tool: extract_project_info — Pattern-Beispiel für alle Pinta-Custom-Tools.

Pattern:
  1. Subclass von ``taskforce.infrastructure.tools.base_tool.BaseTool``.
  2. ``tool_name`` + ``description`` als Class-Attribute — der Agent nutzt
     die Description für seine Tool-Selection-Entscheidung.
  3. Business-Logik ruft bestehende Pinta-Services auf (``AIService``,
     ``RagService``, ``PDFService``) — keine Duplikation.
  4. Keine direkten LLM-Calls hier — der Agent-LLM sitzt eine Ebene höher.
  5. DB-Zugriffe über ``async with`` auf einen frischen Session-Scope,
     nie über globale Session-Objekte.
"""
from typing import Any, Dict, List, Optional
import logging

# TODO: uncomment sobald pytaskforce installiert ist
# from taskforce.infrastructure.tools.base_tool import BaseTool

from src.services.ai_service import AIService

logger = logging.getLogger(__name__)

_ai_service: Optional[AIService] = None


def _get_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


# Temporärer Stub, damit das Modul ohne pytaskforce importierbar bleibt.
# Ersetzen durch: from taskforce.infrastructure.tools.base_tool import BaseTool
class BaseTool:  # pragma: no cover
    name: str = ""          # key in agent.tools-dict und Tool-Registry
    description: str = ""


class ExtractProjectTool(BaseTool):
    """Extrahiert strukturierte Projektdaten aus Freitext des Malers."""

    name = "extract_project_info"
    description = (
        "Extrahiert strukturierte Projektdaten (Raumtyp, Fläche, Höhe, "
        "Zustand, Vorarbeiten, Materialwünsche) aus Freitext und "
        "identifiziert fehlende Informationen für einen Kostenvoranschlag. "
        "Nimmt den kompletten Nutzer-Text als Input; gibt JSON mit "
        "`analysis`, `questions`, `suggestions` zurück."
    )

    # TODO: exakten Method-Namen (execute/run/__call__) + Argument-Schema
    # (JSONSchema als Class-Attribut?) gegen pytaskforce-BaseTool
    # abgleichen — lean_agent.py / base_tool.py checken.
    async def __call__(
        self,
        text: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        service = _get_service()
        return await service.analyze_project_description(
            description=text,
            context="telegram_chat",
            conversation_history=conversation_history or [],
        )
