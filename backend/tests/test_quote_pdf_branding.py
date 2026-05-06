"""Tests für PDF-Branding (Logo + Firmen-Header).

Beide Punkte stehen in TODOList.md ⬜ MVP-Mindest-Checkliste:
- "Logo im PDF rendern: aus User.logo_path lesen, oben links platzieren"
- "Firmen-Header im PDF: company_name + address + vat_id aus User-Profile
  in den Briefkopf"

Aktuell ignoriert ``backend/src/agents/tools/generate_quote_pdf.py:_render_pdf``
sowohl das Logo als auch die Firmen-Daten — die Funktion akzeptiert nur ein
``quote``-Dict und rendert generischen Briefkopf.

Diese Tests definieren das erwartete Verhalten:

1. Wird im Quote-Dict ein ``company``-Sub-Block mit ``company_name`` /
   ``address`` / ``vat_id`` mitgeschickt, müssen diese Werte im
   PDF-Klartext erscheinen.
2. Wird ``company.logo_path`` auf eine existierende PNG gesetzt, muss das
   gerenderte PDF mindestens ein eingebettetes Bild enthalten.
3. Fehlende oder ungültige ``logo_path``-Werte werden stumm geskippt
   (kein Crash, weil das PDF auch ohne Logo nutzbar bleiben muss).
"""
from __future__ import annotations

from pathlib import Path


# 1×1 transparente PNG, hand-codiert. Kein PIL-Dep nötig.
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _base_quote() -> dict:
    """Minimaler valider Quote-Dict, wie der Agent ihn liefert."""
    return {
        "quote_number": "Q-2026-0001",
        "project_title": "Schlafzimmer streichen",
        "project_description": "38 m² Wand und Decke weiß",
        "customer_name": "Erika Musterfrau",
        "items": [
            {
                "position": 1,
                "description": "Wand und Decke streichen",
                "quantity": 38,
                "unit": "m²",
                "unit_price": 25.0,
                "total_price": 950.0,
            },
        ],
        "subtotal": 950.0,
        "vat_amount": 180.5,
        "total_amount": 1130.5,
    }


def _extract_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _count_pdf_images(pdf_path: Path) -> int:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return sum(len(page.images) for page in reader.pages)


# --- Firmen-Header ----------------------------------------------------


def test_pdf_renders_company_name_in_header(tmp_path: Path) -> None:
    """Wenn ``quote.company.company_name`` gesetzt ist, muss er im PDF stehen."""
    from src.agents.tools.generate_quote_pdf import _render_pdf

    quote = _base_quote()
    quote["company"] = {
        "company_name": "Maler Müller GmbH",
        "address": "Musterstraße 1, 12345 Berlin",
        "vat_id": "DE123456789",
    }
    out = tmp_path / "quote.pdf"
    _render_pdf(quote, out)

    text = _extract_pdf_text(out)
    assert "Maler Müller GmbH" in text, (
        f"Erwartete company_name nicht im PDF-Text. Auszug:\n{text[:500]}"
    )
    assert "Musterstraße 1, 12345 Berlin" in text
    assert "DE123456789" in text


def test_pdf_renders_without_company_block_silently(tmp_path: Path) -> None:
    """Quote ohne company-Block: PDF wird trotzdem erzeugt, ohne Crash."""
    from src.agents.tools.generate_quote_pdf import _render_pdf

    out = tmp_path / "quote.pdf"
    _render_pdf(_base_quote(), out)

    assert out.is_file()
    assert out.stat().st_size > 0


def test_pdf_renders_partial_company_block(tmp_path: Path) -> None:
    """Nur company_name gesetzt — die anderen Felder fallen einfach weg."""
    from src.agents.tools.generate_quote_pdf import _render_pdf

    quote = _base_quote()
    quote["company"] = {"company_name": "Solo Maler"}
    out = tmp_path / "quote.pdf"
    _render_pdf(quote, out)

    text = _extract_pdf_text(out)
    assert "Solo Maler" in text


# --- Logo --------------------------------------------------------------


def test_pdf_embeds_logo_when_logo_path_set(tmp_path: Path) -> None:
    """``quote.company.logo_path`` zeigt auf existierende PNG → Bild im PDF."""
    from src.agents.tools.generate_quote_pdf import _render_pdf

    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(_TINY_PNG)

    quote = _base_quote()
    quote["company"] = {
        "company_name": "Maler X",
        "logo_path": str(logo_path),
    }
    out = tmp_path / "quote.pdf"
    _render_pdf(quote, out)

    assert _count_pdf_images(out) >= 1, (
        "PDF enthält kein eingebettetes Logo, obwohl logo_path gesetzt war."
    )


def test_pdf_omits_logo_when_logo_path_invalid(tmp_path: Path) -> None:
    """Nicht-existierender logo_path wird stumm geskippt, kein Crash."""
    from src.agents.tools.generate_quote_pdf import _render_pdf

    quote = _base_quote()
    quote["company"] = {
        "company_name": "Maler X",
        "logo_path": str(tmp_path / "does-not-exist.png"),
    }
    out = tmp_path / "quote.pdf"
    _render_pdf(quote, out)

    assert out.is_file()
    # company_name muss trotzdem im PDF stehen
    assert "Maler X" in _extract_pdf_text(out)


def test_pdf_omits_logo_when_logo_path_empty(tmp_path: Path) -> None:
    """Leerer / None logo_path wird wie nicht gesetzt behandelt."""
    from src.agents.tools.generate_quote_pdf import _render_pdf

    quote = _base_quote()
    quote["company"] = {
        "company_name": "Maler X",
        "logo_path": "",
    }
    out = tmp_path / "quote.pdf"
    _render_pdf(quote, out)
    assert out.is_file()
