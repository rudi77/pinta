"""generate_quote_pdf — render a Maler-Quote dict into a printable PDF.

Tool returns the absolute path to the generated PDF so the Telegram runner
(or any other channel) can ship it as a downloadable attachment AND
persists the file as a ``Document`` row attached to the active user (and,
if save_quote_to_db ran first, to the freshly created Quote) so the PDF
becomes discoverable from the Web Dashboard.

Layout (single column A4):
  - Letterhead:  "Kostenvoranschlag <quote_number>" + Datum
  - Customer-Block (optional, falls quote.customer_* gesetzt)
  - Project-Title + project_description (optional)
  - Items-Tabelle:  Pos | Beschreibung | Menge | Einheit | EP netto | GP netto
  - Totals-Block:  Subtotal / MwSt 19% / Gesamtbetrag (brutto)
  - Notes + Recommendations
  - Footer: "Dieses Angebot ist 30 Tage gültig. Preise inkl. 19% MwSt."
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from taskforce.infrastructure.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


# Where to write the PDFs. WORK_DIR sits next to the agent state already
# created by the Maler-Agent factory.
_QUOTES_DIR = (
    Path(__file__).resolve().parents[3] / ".taskforce_maler" / "quotes"
)


def _slugify(value: str, fallback: str = "quote") -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)
    safe = safe.strip("_")
    return safe or fallback


async def _persist_document_record(path: Path, size: int) -> int | None:
    """Insert a Document row pointing at the freshly written PDF.

    Pulls the active user_id from the same ContextVar save_quote_to_db
    uses; if the agent runs outside an HTTP/bot mission (e.g. a CLI
    smoke test), returns None silently.
    """
    from src.agents.tools.save_quote_to_db import current_quote_id, current_user_id

    user_id = current_user_id.get()
    if user_id is None:
        return None

    from sqlalchemy import select
    from src.core.database import AsyncSessionLocal
    from src.models.models import Document, Quote

    try:
        async with AsyncSessionLocal() as db:
            quote_id = current_quote_id.get()
            if quote_id is None:
                # Backward-compatible fallback for ad-hoc tool runs outside
                # the normal save_quote_to_db -> generate_quote_pdf sequence.
                quote_id = (await db.execute(
                    select(Quote.id)
                    .where(Quote.user_id == user_id)
                    .order_by(Quote.id.desc())
                    .limit(1)
                )).scalar_one_or_none()

            doc = Document(
                user_id=user_id,
                filename=path.name,
                original_filename=path.name,
                file_path=str(path),
                file_size=size,
                mime_type="application/pdf",
                processing_status="completed",
                quote_id=quote_id,
            )
            db.add(doc)
            await db.commit()
            return doc.id
    except Exception as exc:
        logger.warning(
            "generate_quote_pdf.persist_document_failed err=%s", exc,
        )
        return None


def _fmt_eur(value: Any) -> str:
    try:
        return f"{float(value):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def _render_pdf(quote: dict, output_path: Path) -> None:
    """Render `quote` into `output_path` using reportlab platypus."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], fontSize=18, leading=22, spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=12, leading=16, spaceBefore=12,
    )
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "Small", parent=styles["BodyText"], fontSize=9, leading=12,
        textColor=colors.grey,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )

    story: list = []
    quote_number = quote.get("quote_number") or quote.get("number") or "ENTWURF"
    title = quote.get("project_title") or "Kostenvoranschlag"
    today = datetime.now().strftime("%d.%m.%Y")

    # Company branding block (logo + header text)
    company = quote.get("company") or {}
    if company:
        logo_path_str = (company.get("logo_path") or "").strip()
        if logo_path_str:
            logo_file = Path(logo_path_str)
            if logo_file.is_file():
                try:
                    story.append(Image(str(logo_file), width=40 * mm, height=20 * mm))
                except Exception:
                    pass

        company_lines = []
        for field in ("company_name", "address", "vat_id"):
            val = (company.get(field) or "").strip()
            if val:
                company_lines.append(val)
        if company_lines:
            story.append(Paragraph("<br/>".join(company_lines), body))
        story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(f"Kostenvoranschlag {quote_number}", title_style))
    story.append(Paragraph(f"Datum: {today}", small))

    # Customer block — only render the lines that are actually filled.
    customer_lines = []
    for key in ("customer_name", "customer_address", "customer_email", "customer_phone"):
        val = (quote.get(key) or "").strip() if isinstance(quote.get(key), str) else ""
        if val:
            customer_lines.append(val)
    if customer_lines:
        story.append(Paragraph("Kunde", h2))
        story.append(Paragraph("<br/>".join(customer_lines), body))

    story.append(Paragraph("Projekt", h2))
    story.append(Paragraph(title, body))
    if quote.get("project_description"):
        story.append(Paragraph(quote["project_description"], body))

    # Items table
    items = quote.get("items") or []
    table_data = [["Pos", "Beschreibung", "Menge", "Einheit", "EP netto", "GP netto"]]
    for idx, item in enumerate(items, start=1):
        try:
            qty = float(item.get("quantity", 0) or 0)
            unit_price = float(item.get("unit_price", 0) or 0)
            total_price = float(item.get("total_price") or qty * unit_price)
        except (TypeError, ValueError):
            qty, unit_price, total_price = 0, 0, 0
        table_data.append([
            str(item.get("position", idx)),
            Paragraph(str(item.get("description", "")), body),
            f"{qty:g}",
            str(item.get("unit", "")),
            _fmt_eur(unit_price),
            _fmt_eur(total_price),
        ])

    items_table = Table(
        table_data,
        colWidths=[10 * mm, 80 * mm, 18 * mm, 18 * mm, 25 * mm, 25 * mm],
        repeatRows=1,
    )
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23395d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fa")]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(Spacer(1, 8))
    story.append(items_table)

    # Totals
    subtotal = quote.get("subtotal")
    vat_amount = quote.get("vat_amount")
    total_amount = quote.get("total_amount")
    if subtotal is None or vat_amount is None or total_amount is None:
        # Fallback compute (shouldn't normally happen — agent owns these)
        subtotal = sum(
            float(i.get("total_price") or 0) for i in items
        )
        vat_amount = round(float(subtotal) * 0.19, 2)
        total_amount = round(float(subtotal) + float(vat_amount), 2)

    totals_table = Table(
        [
            ["Zwischensumme netto", _fmt_eur(subtotal)],
            ["MwSt 19%", _fmt_eur(vat_amount)],
            ["Gesamtbetrag (brutto)", _fmt_eur(total_amount)],
        ],
        colWidths=[120 * mm, 36 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#23395d")),
        ("TOPPADDING", (0, -1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 12))
    story.append(totals_table)

    if quote.get("notes"):
        story.append(Paragraph("Hinweise", h2))
        story.append(Paragraph(str(quote["notes"]).replace("\n", "<br/>"), body))

    recommendations = quote.get("recommendations") or []
    if recommendations:
        story.append(Paragraph("Empfehlungen", h2))
        bullets = "<br/>".join(f"• {r}" for r in recommendations)
        story.append(Paragraph(bullets, body))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Dieses Angebot ist 30 Tage ab Angebotsdatum gültig. Preise inkl. 19% MwSt.<br/>"
        "Verbindliche Endsumme nach Vor-Ort-Besichtigung.",
        small,
    ))

    doc.build(story)


class GenerateQuotePdfTool(BaseTool):
    """Render the agent's quote dict into a downloadable A4 PDF."""

    tool_name = "generate_quote_pdf"
    tool_description = (
        "Erzeugt ein professionelles A4-PDF des fertigen Kostenvoranschlags und "
        "gibt den Datei-Pfad zurück. RUFE DIESES TOOL AUF, sobald du den Quote "
        "fertig kalkuliert hast (mit subtotal, vat_amount, total_amount, items). "
        "Das PDF wird vom Telegram-Bot automatisch dem Nutzer als Download geschickt."
    )
    tool_parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "quote": {
                "type": "object",
                "description": (
                    "Das vollständige Quote-Objekt. Felder: project_title, items "
                    "(Liste mit description/quantity/unit/unit_price/total_price/category), "
                    "subtotal, vat_amount, total_amount, notes, recommendations, "
                    "optional: quote_number, customer_name, customer_address, "
                    "customer_email, customer_phone, project_description."
                ),
            },
            "filename_hint": {
                "type": "string",
                "description": (
                    "Optional: Hinweis für den Dateinamen, z.B. 'schlafzimmer-streichen'. "
                    "Wird zu einem URL-sicheren Slug bereinigt."
                ),
            },
            },
            "required": ["quote"],
        }

    async def _execute(
        self,
        quote: dict[str, Any] | None = None,
        filename_hint: str | None = None,
        **_ignored: Any,
    ) -> dict[str, Any]:
        if not isinstance(quote, dict) or not quote:
            return {
                "success": False,
                "error": (
                    "quote-Argument fehlt. Bitte ruf das Tool mit dem "
                    "vollständigen Quote-Dict auf: "
                    "generate_quote_pdf(quote={...}, filename_hint='...'). "
                    "Das Quote-Dict braucht mindestens project_title, items, "
                    "subtotal, vat_amount, total_amount."
                ),
                "error_type": "MissingArgument",
            }
        try:
            _QUOTES_DIR.mkdir(parents=True, exist_ok=True)
            slug = _slugify(filename_hint or quote.get("project_title", "quote"))
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = _QUOTES_DIR / f"{ts}_{slug[:60]}.pdf"

            _render_pdf(quote, output_path)
            size = output_path.stat().st_size

            # Persist as a Document row attached to the active user (and
            # quote, if save_quote_to_db ran first), so the PDF appears in
            # the Web Dashboard's documents list, not only on the bot's FS.
            document_id = await _persist_document_record(output_path, size)

            return {
                "success": True,
                "file_path": str(output_path),
                "filename": output_path.name,
                "size_bytes": size,
                "document_id": document_id,
                "note": (
                    f"PDF erstellt ({size // 1024} KB). Der Telegram-Bot schickt "
                    "die Datei automatisch im Anschluss als Download. "
                    "Im Web-Dashboard liegt sie unter den Dokumenten."
                    if document_id is not None
                    else f"PDF erstellt ({size // 1024} KB)."
                ),
            }
        except Exception as exc:  # pragma: no cover — surfaced to agent
            logger.exception("generate_quote_pdf failed")
            return {
                "success": False,
                "error": f"PDF-Generierung fehlgeschlagen: {type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
            }
