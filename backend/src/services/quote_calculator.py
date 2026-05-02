"""Deterministic quote arithmetic + plausibility checks.

Replaces the parts of quote generation where the LLM was unreliable:
- summing item totals
- VAT (19% DE) calculation
- per-item total_price = quantity × unit_price
- plausibility ranges for €/m² (Innenraum vs. Fassade) and material amounts

Goal: shrink the LLM's responsibility to "identify positions" and let Python
own the arithmetic. Once pytaskforce-Agent integration starts, this module
becomes the body of the `QuoteCalculator` tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

VAT_RATE_DE = 0.19


@dataclass
class CalculatedQuote:
    items: list[dict]
    subtotal: float
    vat_amount: float
    total_amount: float
    warnings: list[str]


def _round2(value: float) -> float:
    return round(float(value), 2)


def normalize_items(items: Iterable[dict]) -> list[dict]:
    """Recompute each item's total_price = quantity × unit_price.

    LLMs occasionally output total_price that doesn't match qty × unit_price
    (off-by-rounding, off-by-doubling, or copy-paste from another item).
    The normalized total_price is authoritative; the LLM's value is dropped.
    """
    normalized: list[dict] = []
    for raw in items:
        qty = float(raw.get("quantity", 0) or 0)
        unit_price = float(raw.get("unit_price", 0) or 0)
        item = dict(raw)
        item["quantity"] = qty
        item["unit_price"] = unit_price
        item["total_price"] = _round2(qty * unit_price)
        normalized.append(item)
    return normalized


def compute_totals(items: Iterable[dict]) -> tuple[float, float, float]:
    """Sum normalized items → (subtotal_net, vat_amount, total_brutto).

    Items must already be normalized (see normalize_items).
    """
    subtotal = _round2(sum(float(i.get("total_price", 0) or 0) for i in items))
    vat = _round2(subtotal * VAT_RATE_DE)
    total = _round2(subtotal + vat)
    return subtotal, vat, total


# Plausibility bands for warnings — mirror the prompt's rules so the
# Calculator and the LLM share one source of truth in code (DE 2026 net).
INNEN_EUR_PER_SQM = (8.0, 40.0)      # Standard 8-15, mit Vorarbeiten 25-40
FASSADE_EUR_PER_SQM = (25.0, 45.0)
HOURLY_RATE = (45.0, 80.0)            # Maler DE 2026 net
MAX_PAUSCHAL_VORARBEITEN = 1500.0     # über dem Wert ist Vorarbeit eher Stunden-Position


def _is_labor_per_sqm(item: dict) -> bool:
    unit = (item.get("unit") or "").lower()
    cat = (item.get("category") or "").lower()
    return cat == "labor" and unit in {"m²", "m2", "qm"}


def _is_labor_hourly(item: dict) -> bool:
    unit = (item.get("unit") or "").lower()
    cat = (item.get("category") or "").lower()
    return cat == "labor" and unit in {"h", "std", "stunde", "stunden"}


def validate_plausibility(items: Iterable[dict], project_type: str = "innen") -> list[str]:
    """Return human-readable warnings for items outside expected ranges.

    Warnings go into the quote's `notes` field so the Maler sees them and
    can correct before sending. Doesn't block — the LLM's number stays,
    but is flagged.
    """
    warnings: list[str] = []
    band = FASSADE_EUR_PER_SQM if project_type.startswith("fassade") else INNEN_EUR_PER_SQM
    lo, hi = band

    for item in items:
        desc = item.get("description", "?")
        unit_price = float(item.get("unit_price", 0) or 0)

        if _is_labor_per_sqm(item):
            if unit_price < lo:
                warnings.append(
                    f"Position '{desc}': {unit_price:.2f} €/m² liegt unter dem üblichen "
                    f"Bereich ({lo:.0f}–{hi:.0f} €/m² für {project_type})."
                )
            elif unit_price > hi:
                warnings.append(
                    f"Position '{desc}': {unit_price:.2f} €/m² liegt über dem üblichen "
                    f"Bereich ({lo:.0f}–{hi:.0f} €/m² für {project_type})."
                )

        if _is_labor_hourly(item):
            if unit_price < HOURLY_RATE[0]:
                warnings.append(
                    f"Position '{desc}': Stundensatz {unit_price:.2f} €/h liegt unter "
                    f"dem üblichen Maler-Satz ({HOURLY_RATE[0]:.0f}–{HOURLY_RATE[1]:.0f} €/h)."
                )
            elif unit_price > HOURLY_RATE[1]:
                warnings.append(
                    f"Position '{desc}': Stundensatz {unit_price:.2f} €/h liegt über "
                    f"dem üblichen Maler-Satz ({HOURLY_RATE[0]:.0f}–{HOURLY_RATE[1]:.0f} €/h)."
                )

    # Cross-check: when both €/m² labor AND hourly labor positions exist for
    # the same scope, that's the Iter-2 mixing bug — flag it.
    has_per_sqm_labor = any(_is_labor_per_sqm(i) for i in items)
    has_hourly_labor = any(_is_labor_hourly(i) for i in items)
    if has_per_sqm_labor and has_hourly_labor:
        warnings.append(
            "Achtung: Quote enthält sowohl €/m²-Lohn- als auch Stunden-Lohn-Positionen. "
            "Das deutet auf Doppelzählung hin — bitte prüfen, ob ein Pfad ausreicht."
        )

    return warnings


def calculate(items: Iterable[dict], project_type: str = "innen") -> CalculatedQuote:
    """End-to-end: normalize items → totals → plausibility warnings."""
    normalized = normalize_items(items)
    subtotal, vat, total = compute_totals(normalized)
    warnings = validate_plausibility(normalized, project_type)
    return CalculatedQuote(
        items=normalized,
        subtotal=subtotal,
        vat_amount=vat,
        total_amount=total,
        warnings=warnings,
    )


def detect_project_type(text: str) -> str:
    """Light heuristic for plausibility-band selection. Defaults to innen."""
    lowered = (text or "").lower()
    if any(kw in lowered for kw in ("fassade", "außen", "aussen", "außenwand")):
        return "fassade"
    return "innen"
