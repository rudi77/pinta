"""Minimal smoke test for the Maler-Agent via pytaskforce.

Confirms the full path: settings → env-bridge → AgentFactory → Maler-Agent
→ python tool → ExecutionResult.

Fast feedback loop while wiring the agent up. If this fails, fix here before
running the full iter4_agent.py scenario sweep.
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
# Drop a stale OPENAI_API_KEY shell var so settings reads the .env value;
# pytaskforce uses Azure (per maler.yaml) so the OpenAI key is irrelevant
# but the cleanup avoids confusion if you later switch llm.provider to openai.
os.environ.pop("OPENAI_API_KEY", None)


async def main():
    from src.agents.factory import create_maler_agent, warm_factory
    from src.core.settings import settings

    print(f"Using model alias: {settings.agent_llm_model_alias}")
    print(f"Max steps: {settings.agent_max_steps}")

    warm_factory()
    agent = await create_maler_agent()
    print("Agent created. Tools:", list(agent.tools.keys()) if isinstance(agent.tools, dict) else agent.tools)

    try:
        result = await agent.execute(
            mission=(
                "Berechne mit dem python-Tool: Eine Wohnung hat 78 m² Wohnfläche. "
                "Wie groß ist die Streichfläche (Wand + Decke), wenn Wandfläche ≈ 2.4 × "
                "Wohnfläche und Deckenfläche ≈ Wohnfläche? Antworte mit einer Zahl in m²."
            ),
            session_id="smoke-001",
        )
        print("\n=== RESULT ===")
        print(f"Status: {result.status}")
        print(f"Final message: {result.final_message[:500]}")
        print(f"Token usage: {result.token_usage}")
    finally:
        try:
            await agent.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
