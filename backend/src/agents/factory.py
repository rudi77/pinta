"""Maler-Agent Factory.

Invarianten (aus pytaskforce-Source bestätigt):

- ``AgentFactory`` ist der CACHE-Punkt. Sie kapselt teure Infrastruktur:
  LiteLLM-Service mit Connection-Pool, MCP-Connections, Tool-Registry,
  ProfileLoader. Einmal beim FastAPI-Startup instanziieren, wiederverwenden.
- ``LeanAgent``-Instanzen sind **NICHT** für parallele Missions geeignet —
  ``self.context.messages`` wird bei jedem ``execute_stream`` via
  ``initialize() → clear() + extend()`` gestompt. Zwei parallele Chats auf
  derselben Instanz überschreiben sich die Message-Buffer gegenseitig.
  → Pro Telegram-Message ein frischer Agent, danach ``await agent.close()``.
- Custom-Tools werden EINMAL beim Startup in die globale Tool-Registry
  eingetragen (``register_pinta_tools``). Das ``_openai_tools``-Schema wird
  im ``LeanAgent.__init__`` eingefroren — nachträgliches
  ``agent.tools[...] = ...`` sieht der LLM nicht mehr.

Lifecycle::

    # once at startup (main.py lifespan):
    register_pinta_tools()
    warm_factory()

    # per Telegram-Message:
    agent = await create_maler_agent()
    try:
        async for event in agent.execute_stream(mission=..., session_id=...):
            ...
    finally:
        await agent.close()
"""
from pathlib import Path
from typing import Any, Optional
import yaml

# TODO: uncomment once pytaskforce is installed
# from taskforce.application.factory import AgentFactory
# from taskforce.infrastructure.tools.registry import get_tool_registry

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
MALER_CONFIG = AGENTS_DIR / "maler.yaml"

_factory: Optional[Any] = None          # AgentFactory singleton
_tools_registered: bool = False


# --- Config loader --------------------------------------------------------

def _load_config() -> dict:
    with MALER_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- Tool registration (startup-only) -------------------------------------

def register_pinta_tools() -> None:
    """Register Pinta custom tools with the global pytaskforce tool-registry.

    MUST run exactly once at FastAPI startup (lifespan), BEFORE the first
    ``create_agent`` call. Post-hoc ``agent.tools[name] = tool`` umgeht die
    OpenAI-Tool-Schema-Generation und wird vom LLM ignoriert.
    """
    global _tools_registered
    if _tools_registered:
        return

    # Lazy imports: Tool-Module importieren src.services.* — nicht auf Modul-
    # Ebene auflösen, um Zirkelimporte beim Package-Laden zu vermeiden.
    from src.agents.tools.extract_project import ExtractProjectTool  # noqa: F401
    # TODO zug-um-zug:
    # from src.agents.tools.search_materials import SearchMaterialsTool
    # from src.agents.tools.visual_estimate import VisualEstimateTool
    # from src.agents.tools.calculate_quote import CalculateQuoteTool
    # from src.agents.tools.save_draft import SaveDraftTool
    # from src.agents.tools.generate_pdf import GeneratePdfTool

    # registry = get_tool_registry()
    # registry.register(ExtractProjectTool)
    # registry.register(SearchMaterialsTool)
    # ...
    _tools_registered = True
    raise NotImplementedError(
        "Tool-Registry-API gegen pytaskforce verifizieren: exakte Signatur "
        "von get_tool_registry().register(...) — Class oder Instance?"
    )


# --- Factory lifecycle ----------------------------------------------------

def warm_factory() -> None:
    """Pre-warm the shared AgentFactory at startup. Idempotent."""
    global _factory
    if _factory is not None:
        return
    # _factory = AgentFactory()
    raise NotImplementedError(
        "AgentFactory()-Konstruktor einkommentieren, wenn pytaskforce "
        "als dependency installiert ist."
    )


def _get_factory() -> Any:
    if _factory is None:
        raise RuntimeError(
            "AgentFactory nicht initialisiert — warm_factory() aus "
            "FastAPI-lifespan aufrufen."
        )
    return _factory


# --- Per-mission agent creation ------------------------------------------

async def create_maler_agent() -> Any:
    """Create a FRESH Maler-Agent for exactly one mission.

    Caller is responsible for ``await agent.close()`` in a finally-Block —
    sonst leaken MCP-Connections und Runtime-Tracker-Referenzen.
    """
    factory = _get_factory()
    cfg = _load_config()

    # Variante A — Pinta-Inline (aktuell bevorzugt): Config lebt im Pinta-Repo.
    # tool_names = [t["name"] for t in cfg.get("tools", [])]
    # agent = await factory.create_agent(
    #     system_prompt=cfg["system_prompt"],
    #     tools=tool_names,
    #     work_dir=".pinta_agent",
    # )
    # Variante B — pytaskforce-Profile: nur sinnvoll, wenn wir pytaskforce
    # mitteilen können, zusätzlich in backend/agents/ nach Profilen zu suchen.
    # agent = await factory.create_agent(config="maler")
    # return agent

    raise NotImplementedError(
        "create_agent-Aufruf einkommentieren — Variante A (inline) ist der "
        "empfohlene Startpunkt, weil die Config dann mit Pinta versioniert ist."
    )
