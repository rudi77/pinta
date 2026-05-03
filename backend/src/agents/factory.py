"""Maler-Agent Factory.

Pinta uses pytaskforce in **library mode** per the Mode A pattern in
``pytaskforce/docs/integration-guide.md``. The integration goes ONLY
through the public ``taskforce.host`` API (plus ``AgentFactory`` from
``taskforce.application.factory`` which Mode A explicitly allows).

Lifecycle invariants from the guide:

- ``AgentFactory`` is the cache point. Build it ONCE at startup
  (FastAPI lifespan), reuse for every request. Holds the LiteLLM
  connection pool, tool registry, ProfileLoader.
- One ``Agent`` per mission. The agent's message history initialises
  on each ``execute()``; sharing an agent across parallel chats
  corrupts the buffer.
- Always ``await agent.close()`` in a finally block — otherwise MCP
  connections and the runtime tracker leak.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from taskforce.host import (
    is_tool_registered,
    register_profile_dir,
    register_tool,
)

from src.agents.taskforce_setup import ensure_litellm_env_for_taskforce
from src.core.settings import settings

# Pinta's profile directory; pytaskforce's ProfileLoader picks ``maler.yaml``
# (or ``maler.agent.md``) up from here once registered.
AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
WORK_DIR = Path(__file__).resolve().parents[2] / ".taskforce_maler"
PROFILE_NAME = "maler"

_factory: Optional[Any] = None  # AgentFactory singleton
_setup_done: bool = False


def _setup_pinta() -> None:
    """Idempotent: register Pinta tools + profile directory.

    Must run BEFORE the first ``factory.create_agent()`` call so the
    ProfileLoader and tool registry know about our additions.
    """
    global _setup_done
    if _setup_done:
        return

    # Custom tools — name + class + module. ``register_tool`` is idempotent
    # per the host API contract, so calling this on every warm is safe.
    for name, tool_type, module in (
        ("search_materials", "SearchMaterialsTool", "src.agents.tools.search_materials"),
        ("save_quote_to_db", "SaveQuoteToDbTool", "src.agents.tools.save_quote_to_db"),
        ("generate_quote_pdf", "GenerateQuotePdfTool", "src.agents.tools.generate_quote_pdf"),
    ):
        if not is_tool_registered(name):
            register_tool(name=name, tool_type=tool_type, module=module)

    # Tell pytaskforce's ProfileLoader where to find our maler profile.
    register_profile_dir(str(AGENTS_DIR))

    _setup_done = True


def warm_factory() -> Any:
    """Pre-warm the shared AgentFactory at startup. Idempotent.

    Lazy-imports pytaskforce so test environments without the dep can still
    import the rest of the agents package (e.g. for tool unit tests).
    """
    global _factory
    if _factory is not None:
        return _factory

    ensure_litellm_env_for_taskforce(strict=True)
    _setup_pinta()

    # AgentFactory direct import is sanctioned for Mode A by the integration
    # guide (the ``taskforce.host`` module's docstring §10 explicitly says
    # "import AgentFactory directly").
    from taskforce.application.factory import AgentFactory  # noqa: WPS433

    _factory = AgentFactory()
    return _factory


def _get_factory() -> Any:
    if _factory is None:
        return warm_factory()
    return _factory


async def create_maler_agent(*, tools: Optional[list[str]] = None) -> Any:
    """Create a FRESH Maler-Agent for exactly one mission.

    Caller MUST ``await agent.close()`` in a finally-Block (lifecycle
    invariant from the integration guide §4.2).

    The agent is built from the ``maler`` profile (``backend/agents/maler.yaml``)
    registered above. ``tools`` argument is an optional override for tests;
    production code should leave it ``None`` and edit the YAML instead.
    """
    factory = _get_factory()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    if tools is None:
        agent = await factory.create_agent(
            profile=PROFILE_NAME, work_dir=str(WORK_DIR),
        )
    else:
        # Tests / escape hatch — explicit tool list, profile is ignored.
        agent = await factory.create_agent(
            profile=PROFILE_NAME, tools=tools, work_dir=str(WORK_DIR),
        )
    return agent


# ---------------------------------------------------------------------------
# Backwards-compat shim — older code in this repo (and external scripts)
# imported register_pinta_tools directly. Keep it as a thin alias so we
# don't break those call sites while the host-API rewrite settles in.
# ---------------------------------------------------------------------------

def register_pinta_tools() -> None:
    """Deprecated alias for ``_setup_pinta``. Use ``warm_factory`` instead."""
    _setup_pinta()
