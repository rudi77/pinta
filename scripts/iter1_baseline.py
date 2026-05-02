"""Iteration 1 Baseline — drives 3 realistic Maler scenarios through AIService.

Runs both flows:
  A) generate_quick_quote        (single-shot MVP path)
  B) analyze_project_description -> process_answers_and_generate_quote
                                   (multi-turn path with simulated answers)

Outputs each result as JSON under iteration_logs/iter1_baseline/.
No FastAPI / DB needed — direct service calls keep the loop cheap and
deterministic to compare across iterations.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = REPO_ROOT / "backend" / "src"
# Output directory is overridable via ITER_LOG_DIR so the same script can run
# both as baseline and as post-fix re-run without losing the previous outputs.
LOG_DIR = REPO_ROOT / "iteration_logs" / os.environ.get(
    "ITER_LOG_DIR", "iter1_baseline"
)
sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(REPO_ROOT / "backend"))
# Iteration scripts run with strict mode so silent mock fallbacks don't mask
# real bugs (broken prompts, expired API keys, etc.). Must be set BEFORE the
# Settings singleton is built by importing ai_service.
os.environ.setdefault("AI_STRICT_MODE", "true")

# Pydantic-settings prefers process ENV vars over .env contents. If the user
# updated backend/.env to fix an expired key, a stale OPENAI_API_KEY in the
# shell environment would silently win. Drop it so the .env value is used.
os.environ.pop("OPENAI_API_KEY", None)

# Realistic Maler scenarios — picked to cover Output-Quality / Domain-Correctness
# attack surface (the two clusters most likely to kill a real Maler test).
SCENARIOS = [
    {
        "id": "S1_simple_room",
        "label": "Einzelnes Schlafzimmer streichen",
        "service_description": (
            "Ein Schlafzimmer komplett streichen, Wände und Decke. "
            "Aktuelle Farbe ist eine alte gelbliche Dispersion, soll jetzt "
            "weiß werden. Standard-Qualität."
        ),
        "area": "Raum 4,2 m × 3,5 m, Deckenhöhe 2,55 m, ein Fenster (1,2×1,4 m) "
                "und eine Tür.",
        "additional_info": "Möbel werden vom Kunden ausgeräumt. Boden ist Laminat — abdecken nötig.",
        # Multi-turn synthetic answers — simulate what user would say after
        # follow-up questions
        "answers": [
            {"question_id": "area", "answer": "ca. 14,7 m² Boden, 39 m² Wandfläche, 14,7 m² Decke"},
            {"question_id": "prep", "answer": "keine Risse, alte Farbe ist gleichmäßig, also nur leichte Vorarbeit"},
            {"question_id": "material", "answer": "Standard-Dispersion, weiß"},
            {"question_id": "timeline", "answer": "innerhalb der nächsten 2 Wochen"},
        ],
    },
    {
        "id": "S2_apartment_renovation",
        "label": "3-Zi-Wohnung Renovierung mit Vorarbeiten",
        "service_description": (
            "Komplette 3-Zimmer-Wohnung renovieren: Wohnzimmer, Schlafzimmer, "
            "Kinderzimmer, Flur und Küche. Wände haben Risse von alter Tapete, "
            "an einer Stelle Wasserfleck (vermutlich kein aktiver Schaden). "
            "Decken sollen mit, Türen und Fenster ausgespart."
        ),
        "area": "Wohnung 78 m² Wohnfläche. Räume zwischen 8 und 22 m². Deckenhöhe überall 2,60 m.",
        "additional_info": (
            "Wohnung wird zwischen zwei Mietverträgen renoviert, also leer. "
            "Kunde hätte gerne Premium-Farbe weil Allergiker. "
            "Heizkörper bleiben dran, sollen umstrichen werden."
        ),
        "answers": [
            {"question_id": "area", "answer": "Wohnzimmer 22 m², Schlaf 14 m², Kinder 12 m², Flur 8 m², Küche 9 m². Gesamt-Wandfläche ca. 175 m², Decken ca. 65 m²"},
            {"question_id": "prep", "answer": "Risse müssen gespachtelt werden, Wasserfleck mit Isoliergrundierung behandeln, sonst gut"},
            {"question_id": "material", "answer": "Premium-Allergiker-Dispersion (z.B. Alpina Allergiker oder vergleichbar), weiß matt"},
            {"question_id": "access", "answer": "leerstehend, EG, gute Zugänglichkeit"},
            {"question_id": "timeline", "answer": "10 Werktage Zeitfenster"},
        ],
    },
    {
        "id": "S3_facade_outdoor",
        "label": "Fassadenanstrich Einfamilienhaus",
        "service_description": (
            "Außenfassade Einfamilienhaus neu streichen. Aktuell verwitterter "
            "Silikat-Anstrich aus 2008, an Wetterseite Algenbefall, sonst gut. "
            "Holzfensterläden sollen mitgemacht werden."
        ),
        "area": (
            "Haus 9 m × 11 m Grundfläche, 2 Vollgeschosse + ausgebauter Spitzboden. "
            "Geschätzte Fassadenfläche ca. 240 m² netto (Fenster und Türen abgezogen). "
            "12 Holzfensterläden je ca. 1,2 m × 0,6 m."
        ),
        "additional_info": (
            "Gerüst muss gestellt werden, Haus steht auf einem Grundstück mit "
            "ausreichend Platz drumrum. Kunde wünscht warmes Cremegelb. "
            "Algenbefall mit Algenentferner vorbehandeln."
        ),
        "answers": [
            {"question_id": "area", "answer": "240 m² Fassade, 12 Fensterläden ca. 17 m² Holzfläche gesamt"},
            {"question_id": "substrate", "answer": "Silikat-Anstrich tragfähig, nur Algenbefall an Nord- und Westseite (~80 m²)"},
            {"question_id": "material", "answer": "Silikatfarbe wegen Atmungsaktivität, Cremegelb (z.B. Keim Soldalit oder Sto-Sil)"},
            {"question_id": "scaffolding", "answer": "Gerüst Standzeit 2 Wochen, ca. 240 m² Gerüstfläche"},
            {"question_id": "timeline", "answer": "Sommermonate, idealerweise Juli/August 2026"},
        ],
    },
]


def emit(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def banner(text: str) -> None:
    print("=" * 78)
    print(text)
    print("=" * 78)


async def run_quick_quote(ai_service, scenario: dict) -> dict:
    t0 = time.perf_counter()
    result = await ai_service.generate_quick_quote(
        service_description=scenario["service_description"],
        area=scenario.get("area"),
        additional_info=scenario.get("additional_info"),
        hourly_rate=None,
        material_cost_markup=None,
    )
    elapsed = time.perf_counter() - t0
    return {"scenario_id": scenario["id"], "label": scenario["label"],
            "elapsed_seconds": round(elapsed, 2), "result": result}


async def run_multiturn(ai_service, scenario: dict) -> dict:
    t0 = time.perf_counter()
    analysis = await ai_service.analyze_project_description(
        description=scenario["service_description"],
        context="initial_input",
        conversation_history=None,
    )

    project_data = {
        "description": scenario["service_description"],
        "area": scenario.get("area"),
        "additional_info": scenario.get("additional_info"),
    }
    quote = await ai_service.process_answers_and_generate_quote(
        project_data=project_data,
        answers=scenario["answers"],
        conversation_history=None,
        document_files=None,
        hourly_rate=None,
        material_cost_markup=None,
        material_context=None,  # Phase 1 baseline: no RAG
    )
    elapsed = time.perf_counter() - t0
    return {"scenario_id": scenario["id"], "label": scenario["label"],
            "elapsed_seconds": round(elapsed, 2),
            "analysis": analysis, "quote": quote}


async def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Import after sys.path setup
    from src.services.ai_service import AIService

    ai_service = AIService()
    banner(f"AI service status: enabled={ai_service.enabled} model={ai_service.model}")
    if not ai_service.enabled:
        print("WARNING: OPENAI_API_KEY not set — running in mock mode.")
        print("Mock outputs are deterministic placeholders, NOT useful for quality eval.")
        print("Set OPENAI_API_KEY in backend/.env and rerun.")

    summary = {"ai_enabled": ai_service.enabled, "model": ai_service.model,
               "scenarios": []}

    for scenario in SCENARIOS:
        banner(f"[{scenario['id']}] {scenario['label']}")

        print("Flow A: generate_quick_quote ...")
        try:
            quick = await run_quick_quote(ai_service, scenario)
            emit(LOG_DIR / f"{scenario['id']}_quick.json", quick)
            items = quick["result"].get("items", [])
            total = quick["result"].get("total_amount", 0)
            print(f"  -> {len(items)} items, total {total:.2f} EUR, "
                  f"{quick['elapsed_seconds']}s")
        except Exception as e:
            print(f"  !! quick_quote failed: {type(e).__name__}: {e}")
            quick = {"error": f"{type(e).__name__}: {e}"}
            emit(LOG_DIR / f"{scenario['id']}_quick.json", quick)

        print("Flow B: analyze_project + process_answers_and_generate_quote ...")
        try:
            multi = await run_multiturn(ai_service, scenario)
            emit(LOG_DIR / f"{scenario['id']}_multiturn.json", multi)
            qd = multi["quote"]
            items = qd.get("items", [])
            print(f"  -> analysis questions: {len(multi['analysis'].get('questions', []))}")
            print(f"  -> quote items: {len(items)}, "
                  f"total {qd.get('quote', {}).get('total_amount', 0):.2f} EUR, "
                  f"{multi['elapsed_seconds']}s")
        except Exception as e:
            print(f"  !! multiturn failed: {type(e).__name__}: {e}")
            multi = {"error": f"{type(e).__name__}: {e}"}
            emit(LOG_DIR / f"{scenario['id']}_multiturn.json", multi)

        summary["scenarios"].append({
            "id": scenario["id"],
            "label": scenario["label"],
            "quick_ok": "error" not in quick,
            "multiturn_ok": "error" not in multi,
        })

    emit(LOG_DIR / "_summary.json", summary)
    banner("Done. Outputs under iteration_logs/iter1_baseline/")


if __name__ == "__main__":
    asyncio.run(main())
