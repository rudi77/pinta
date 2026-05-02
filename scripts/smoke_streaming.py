"""Smoke-Test for agent.execute_stream — confirms what events look like
in the wild, so the Telegram bot and (later) SSE endpoints know what to
filter for. Streams S1 (smallest scenario) and prints each event type
plus a snippet of its payload.
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
os.environ.pop("OPENAI_API_KEY", None)


MISSION = (
    "Erstelle einen Kostenvoranschlag: Schlafzimmer 14,7 m² Wohnfläche, "
    "Wandfläche 39 m², Decke 14,7 m², Streichfläche 53,7 m². "
    "Standard-Dispersion weiß, leichte Vorarbeit. Stundensatz 55 €/h. "
    "JSON-Format wie im System-Prompt."
)


def _short(value, n: int = 140) -> str:
    s = repr(value)
    return s if len(s) <= n else s[:n] + "..."


async def main():
    from src.agents.factory import create_maler_agent, warm_factory

    warm_factory()
    agent = await create_maler_agent()
    print("Agent ready. Streaming...\n")

    counts: dict[str, int] = {}
    final_message_buffer: list[str] = []
    try:
        async for event in agent.execute_stream(
            mission=MISSION,
            session_id="stream-smoke-001",
        ):
            etype = (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            )
            counts[etype] = counts.get(etype, 0) + 1

            if etype == "llm_token":
                # Print incrementally without newline
                tok = event.data.get("token") or event.data.get("content") or ""
                final_message_buffer.append(tok)
                print(tok, end="", flush=True)
            elif etype == "tool_call":
                print(f"\n[TOOL_CALL] {_short(event.data)}")
            elif etype == "tool_result":
                print(f"[TOOL_RESULT] {_short(event.data)}")
            elif etype == "step_start":
                step = event.data.get("step", "?")
                print(f"\n--- step {step} ---")
            elif etype == "final_answer":
                print(f"\n[FINAL_ANSWER] {_short(event.data, 200)}")
            elif etype == "error":
                print(f"\n[ERROR] {_short(event.data, 300)}")
            elif etype == "token_usage":
                print(f"\n[TOKEN_USAGE] {event.data}")
            else:
                print(f"\n[{etype.upper()}] {_short(event.data)}")
    finally:
        try:
            await agent.close()
        except Exception:
            pass

    print("\n\n" + "=" * 70)
    print("Event-Type Counts:")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    print("=" * 70)
    print(f"Streamed text length: {len(''.join(final_message_buffer))} chars")


if __name__ == "__main__":
    asyncio.run(main())
