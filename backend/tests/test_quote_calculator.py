"""Unit tests for the deterministic quote calculator.

The calculator owns the arithmetic that the LLM kept getting wrong:
- per-item total_price = qty × unit_price (LLM had drift / copy-paste errors)
- subtotal / VAT / total_amount (LLM mixed net and brutto)
- plausibility ranges (LLM picked 5 €/m² for a fassade once and 50 €/m² another time)

Tests target each of those failure modes plus the iter-2 mixing-detection.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("AI_STRICT_MODE", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-test_dummy_key")

from src.services import quote_calculator as qc  # noqa: E402


def test_normalize_recomputes_total_price():
    """LLM may emit total_price that doesn't match qty × unit_price; we override."""
    items = [{"description": "x", "quantity": 10, "unit": "m²", "unit_price": 12.5,
              "total_price": 999.99}]
    out = qc.normalize_items(items)
    assert out[0]["total_price"] == 125.0


def test_compute_totals_applies_19pct_vat():
    items = [
        {"quantity": 1, "unit_price": 100.0, "total_price": 100.0},
        {"quantity": 2, "unit_price": 50.0, "total_price": 100.0},
    ]
    sub, vat, total = qc.compute_totals(items)
    assert sub == 200.0
    assert vat == 38.0
    assert total == 238.0


def test_calculate_end_to_end_flat_envelope():
    items = [
        {"description": "Streichen", "quantity": 50, "unit": "m²",
         "unit_price": 12.0, "category": "labor"},
        {"description": "Farbe", "quantity": 10, "unit": "L",
         "unit_price": 8.0, "category": "material"},
    ]
    calc = qc.calculate(items)
    assert calc.subtotal == 680.0
    assert calc.vat_amount == 129.2
    assert calc.total_amount == 809.2
    assert len(calc.items) == 2
    # No plausibility violation here (12 €/m² is in 8–40 innen band)
    assert calc.warnings == []


def test_warns_on_labor_per_sqm_below_band():
    items = [{"description": "Streichen", "quantity": 100, "unit": "m²",
              "unit_price": 5.0, "category": "labor"}]
    calc = qc.calculate(items, project_type="innen")
    assert any("liegt unter" in w for w in calc.warnings)


def test_warns_on_labor_per_sqm_above_band():
    items = [{"description": "Streichen", "quantity": 50, "unit": "m²",
              "unit_price": 60.0, "category": "labor"}]
    calc = qc.calculate(items, project_type="innen")
    assert any("liegt über" in w for w in calc.warnings)


def test_warns_on_hourly_rate_below_band():
    items = [{"description": "Lohn", "quantity": 10, "unit": "h",
              "unit_price": 30.0, "category": "labor"}]
    calc = qc.calculate(items)
    assert any("Stundensatz" in w and "unter" in w for w in calc.warnings)


def test_warns_on_mixed_labor_units():
    """Iter-2 bug: LLM mixes €/m² labor AND hourly labor for the same scope."""
    items = [
        {"description": "Streichen Pauschal", "quantity": 50, "unit": "m²",
         "unit_price": 12.0, "category": "labor"},
        {"description": "Lohn extra", "quantity": 10, "unit": "h",
         "unit_price": 55.0, "category": "labor"},
    ]
    calc = qc.calculate(items)
    assert any("Doppelzählung" in w for w in calc.warnings)


def test_fassade_uses_higher_band():
    """25 €/m² is below innen band's upper edge but in fassade band — no warning."""
    items = [{"description": "Fassade", "quantity": 240, "unit": "m²",
              "unit_price": 30.0, "category": "labor"}]
    calc = qc.calculate(items, project_type="fassade")
    assert calc.warnings == []


def test_detect_project_type_handles_fassade():
    assert qc.detect_project_type("Außenfassade neu streichen") == "fassade"
    assert qc.detect_project_type("Aussenwand erneuern") == "fassade"
    assert qc.detect_project_type("Schlafzimmer streichen") == "innen"
    assert qc.detect_project_type("") == "innen"
