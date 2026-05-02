"""Iteration 4 — same 3 Maler scenarios but driven through the pytaskforce
Maler-Agent (Azure / gpt-5.4-mini + python tool).

Compares against iter3_calculator/ outputs to see whether moving the math
into a real tool-use loop improves or regresses the quote quality.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
LOG_DIR = REPO_ROOT / "iteration_logs" / os.environ.get("ITER_LOG_DIR", "iter4_agent")
os.environ.pop("OPENAI_API_KEY", None)


# Same scenarios as iter1_baseline.py so the deltas are apples-to-apples.
SCENARIOS = [
    {
        "id": "S1_simple_room",
        "label": "Einzelnes Schlafzimmer streichen",
        "mission": (
            "Erstelle einen Kostenvoranschlag für folgendes Projekt:\n"
            "Ein Schlafzimmer komplett streichen, Wände und Decke. "
            "Aktuelle Farbe ist eine alte gelbliche Dispersion, soll jetzt weiß werden. Standard-Qualität.\n"
            "Maße: Raum 4,2 m × 3,5 m, Deckenhöhe 2,55 m, ein Fenster (1,2 × 1,4 m) und eine Tür.\n"
            "Wandfläche ca. 39 m², Decke ca. 14,7 m². Streichfläche gesamt ca. 53,7 m².\n"
            "Möbel werden vom Kunden ausgeräumt. Boden ist Laminat — abdecken nötig.\n"
            "Standard-Dispersionsfarbe weiß, leichte Vorarbeit, Stundensatz 55 €/h.\n"
            "Gib mir den Voranschlag im im System-Prompt definierten JSON-Format zurück."
        ),
    },
    {
        "id": "S2_apartment_renovation",
        "label": "3-Zi-Wohnung Renovierung mit Vorarbeiten",
        "mission": (
            "Erstelle einen Kostenvoranschlag für folgendes Projekt:\n"
            "Komplette 3-Zimmer-Wohnung renovieren: Wohnzimmer (22 m²), Schlafzimmer (14 m²), "
            "Kinderzimmer (12 m²), Flur (8 m²), Küche (9 m²). Wohnfläche gesamt 78 m². "
            "Wände haben Risse von alter Tapete, an einer Stelle Wasserfleck (vermutlich kein aktiver Schaden). "
            "Decken sollen mit, Türen und Fenster ausgespart. Deckenhöhe überall 2,60 m.\n"
            "Wandfläche ca. 175 m², Deckenfläche ca. 65 m². Streichfläche gesamt ca. 240 m².\n"
            "Wohnung leerstehend, EG, gute Zugänglichkeit. 10 Werktage Zeitfenster.\n"
            "Premium-Allergiker-Dispersion weiß matt. Risse spachteln, Wasserfleck mit Isoliergrund. "
            "Heizkörper (5 Stück) bleiben dran, sollen umstrichen werden. Stundensatz 55 €/h.\n"
            "Gib mir den Voranschlag im im System-Prompt definierten JSON-Format zurück."
        ),
    },
    {
        "id": "S3_facade_outdoor",
        "label": "Fassadenanstrich Einfamilienhaus",
        "mission": (
            "Erstelle einen Kostenvoranschlag für folgendes Projekt:\n"
            "Außenfassade Einfamilienhaus neu streichen. Aktuell verwitterter Silikat-Anstrich aus 2008, "
            "an Wetterseite (Nord/West, ~80 m²) Algenbefall, sonst gut. "
            "Holzfensterläden (12 Stück, ca. 17 m² Holzfläche gesamt) sollen mitgemacht werden.\n"
            "Haus 9 m × 11 m Grundfläche, 2 Vollgeschosse + ausgebauter Spitzboden. "
            "Fassadenfläche ca. 240 m² netto (Fenster und Türen abgezogen).\n"
            "Gerüst muss gestellt werden, 2 Wochen Standzeit. Genug Platz drumrum.\n"
            "Cremegelb. Silikatfarbe (z.B. Keim Soldalit). Algenbefall mit Algenentferner vorbehandeln. "
            "Sommermonate Juli/August 2026. Stundensatz 55 €/h.\n"
            "Gib mir den Voranschlag im im System-Prompt definierten JSON-Format zurück."
        ),
    },
]


def _extract_json_blob(text: str) -> dict | None:
    """Pick the largest balanced JSON object out of free-form agent output."""
    if not text:
        return None
    # Try fenced ```json ... ``` first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: greedy match the outermost {...}
    matches = re.findall(r"\{.*\}", text, re.DOTALL)
    for blob in sorted(matches, key=len, reverse=True):
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            continue
    return None


def emit(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def banner(text: str) -> None:
    print("=" * 78)
    print(text)
    print("=" * 78)


async def run_scenario(scenario: dict) -> dict:
    from src.agents.factory import create_maler_agent

    agent = await create_maler_agent()
    t0 = time.perf_counter()
    try:
        result = await agent.execute(
            mission=scenario["mission"],
            session_id=f"iter4-{scenario['id']}",
        )
    finally:
        try:
            await agent.close()
        except Exception:
            pass

    elapsed = time.perf_counter() - t0
    quote_json = _extract_json_blob(result.final_message)
    return {
        "scenario_id": scenario["id"],
        "label": scenario["label"],
        "elapsed_seconds": round(elapsed, 2),
        "status": str(result.status),
        "token_usage": {
            "prompt": result.token_usage.prompt_tokens,
            "completion": result.token_usage.completion_tokens,
            "total": result.token_usage.total_tokens,
        },
        "final_message": result.final_message,
        "quote_extracted": quote_json,
    }


async def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    from src.agents.factory import warm_factory
    from src.core.settings import settings

    banner(f"Iter 4 — Maler-Agent (model alias: {settings.agent_llm_model_alias}, max_steps: {settings.agent_max_steps})")
    warm_factory()

    summary = {"model_alias": settings.agent_llm_model_alias, "scenarios": []}

    for scenario in SCENARIOS:
        banner(f"[{scenario['id']}] {scenario['label']}")
        try:
            payload = await run_scenario(scenario)
            emit(LOG_DIR / f"{scenario['id']}.json", payload)
            quote = payload.get("quote_extracted") or {}
            total = quote.get("total_amount", "n/a")
            n_items = len(quote.get("items", []))
            print(f"  -> status={payload['status']}, items={n_items}, total={total}, "
                  f"{payload['elapsed_seconds']}s, tokens={payload['token_usage']['total']}")
            summary["scenarios"].append({
                "id": scenario["id"],
                "status": payload["status"],
                "items": n_items,
                "total": total,
                "tokens": payload["token_usage"]["total"],
                "elapsed_s": payload["elapsed_seconds"],
            })
        except Exception as e:
            print(f"  !! FAILED: {type(e).__name__}: {e}")
            emit(LOG_DIR / f"{scenario['id']}.json", {"error": f"{type(e).__name__}: {e}"})
            summary["scenarios"].append({"id": scenario["id"], "status": "failed", "error": str(e)})

    emit(LOG_DIR / "_summary.json", summary)
    banner(f"Done. Outputs under iteration_logs/{LOG_DIR.name}/")


if __name__ == "__main__":
    asyncio.run(main())
