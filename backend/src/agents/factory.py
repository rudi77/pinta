"""Maler-Agent Factory.

Invarianten (aus pytaskforce-Source bestätigt):

- ``AgentFactory`` ist der CACHE-Punkt. Sie kapselt teure Infrastruktur:
  LiteLLM-Service mit Connection-Pool, Tool-Registry, ProfileLoader. Einmal
  beim FastAPI-Startup instanziieren, wiederverwenden.
- Per Mission ein frischer ``Agent`` (LeanAgent) — die Message-History wird
  bei jedem ``execute()`` initialisiert. Zwei parallele Telegram-Chats auf
  derselben Agent-Instanz würden sich gegenseitig den Kontext zerschießen.
- Nach jedem ``execute()``: ``await agent.close()`` (MCP-Connections und
  Runtime-Tracker leaken sonst).

Lifecycle::

    # once at startup (main.py lifespan):
    warm_factory()

    # per Telegram-Message:
    agent = await create_maler_agent()
    try:
        result = await agent.execute(mission=..., session_id=...)
    finally:
        await agent.close()
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from src.agents.taskforce_setup import ensure_litellm_env_for_taskforce
from src.core.settings import settings

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
MALER_CONFIG = AGENTS_DIR / "maler.yaml"
WORK_DIR = Path(__file__).resolve().parents[2] / ".taskforce_maler"

_factory: Optional[Any] = None  # AgentFactory singleton
_config_cache: Optional[dict] = None
_tools_registered: bool = False


def _load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        with MALER_CONFIG.open(encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def register_pinta_tools() -> None:
    """Register Pinta-specific tools in pytaskforce' global tool registry.

    Idempotent — safe to call multiple times.
    MUST run before the first ``create_agent`` call so the OpenAI tool schema
    includes them (LeanAgent freezes the tool schema at construction time).
    """
    global _tools_registered
    if _tools_registered:
        return

    from taskforce.infrastructure.tools.registry import (  # noqa: WPS433
        _TOOL_REGISTRY,
        register_tool,
    )

    pinta_tools = [
        {
            "name": "search_materials",
            "type": "SearchMaterialsTool",
            "module": "src.agents.tools.search_materials",
        },
        {
            "name": "generate_quote_pdf",
            "type": "GenerateQuotePdfTool",
            "module": "src.agents.tools.generate_quote_pdf",
        },
    ]
    for spec in pinta_tools:
        if spec["name"] in _TOOL_REGISTRY:
            continue  # Already registered — module reload or repeat call
        register_tool(
            name=spec["name"],
            tool_type=spec["type"],
            module=spec["module"],
        )
    _tools_registered = True


def warm_factory() -> Any:
    """Pre-warm the shared AgentFactory at startup. Idempotent.

    Lazy-imports pytaskforce so test environments without the dep can still
    import the rest of the agents package (e.g. for tool unit tests).
    """
    global _factory
    if _factory is not None:
        return _factory

    ensure_litellm_env_for_taskforce(strict=True)
    register_pinta_tools()
    from taskforce.application.factory import AgentFactory  # noqa: WPS433

    _factory = AgentFactory()
    return _factory


def _get_factory() -> Any:
    if _factory is None:
        return warm_factory()
    return _factory


async def create_maler_agent(*, tools: Optional[list[str]] = None) -> Any:
    """Create a FRESH Maler-Agent for exactly one mission.

    Caller MUST ``await agent.close()`` in a finally-Block.

    Args:
        tools: Override the tool list (default: just ``["python"]`` until
            the Pinta-specific Tools — search_materials, visual_estimate,
            calculate_quote, save_draft, generate_pdf — als ToolProtocol-
            Implementierungen registriert sind).
    """
    factory = _get_factory()
    cfg = _load_config()

    # Iter 6: python (math) + search_materials (RAG) + generate_quote_pdf
    # (rendert den Quote als A4-PDF; Telegram-Runner versendet die Datei
    # automatisch als Download, wenn das Tool erfolgreich gelaufen ist).
    tool_list = (
        tools if tools is not None
        else ["python", "search_materials", "generate_quote_pdf"]
    )

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    agent = await factory.create_agent(
        system_prompt=cfg["system_prompt"],
        tools=tool_list,
        max_steps=settings.agent_max_steps,
        work_dir=str(WORK_DIR),
    )
    return agent
