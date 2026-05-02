"""Smoke test for runner._humanize_reply — strips JSON / fences cleanly."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.pop("OPENAI_API_KEY", None)

from src.telegram.runner import _humanize_reply  # noqa: E402

cases = {
    "json-in-fence": (
        "Hier ist dein Voranschlag:\n\n"
        "```json\n"
        "{\n"
        '  "project_title": "80 qm Wohnung weiß streichen",\n'
        '  "items": [{"description": "x", "quantity": 1, "unit": "h", '
        '"unit_price": 55, "total_price": 55}],\n'
        '  "subtotal": 3044.0,\n'
        '  "vat_amount": 578.36,\n'
        '  "total_amount": 3622.36,\n'
        '  "notes": "80 m² Wohnfläche kalkuliert.",\n'
        '  "recommendations": []\n'
        "}\n"
        "```\n"
    ),
    "raw-json-only": (
        '{"project_title": "Test", "subtotal": 100.0, '
        '"vat_amount": 19.0, "total_amount": 119.0, '
        '"notes": "Eine Annahme.", "items": []}'
    ),
    "prose-only": "Mach ich gleich. Voranschlag ist fertig, PDF kommt.",
    "prose-then-json": (
        "Servus, das war ein größeres Projekt.\n\n"
        '{"project_title": "Mit Vorrede", "subtotal": 200, "vat_amount": 38, '
        '"total_amount": 238, "items": []}'
    ),
}

for name, raw in cases.items():
    print(f"\n=== {name} ===")
    print(_humanize_reply(raw))
