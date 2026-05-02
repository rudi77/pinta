import openai
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import base64
from src.core.settings import settings
from src.services import quote_calculator

logger = logging.getLogger(__name__)

class AIService:
    # Domain anchors injected into all quote-generation prompts. Goal: stop the
    # LLM from hallucinating sqm out of "Wohnfläche", and stop pricing from
    # drifting between "5 €/m²" and "50 €/m²" for the same kind of work.
    # Numbers reflect typical DE 2026 net pricing for Maler-Handwerk.
    _PLAUSIBILITY_RULES = """PLAUSIBILITÄTSREGELN (verbindlich für realistische Quoten):

FLÄCHEN-FAUSTREGELN:
- Verwechsle NIEMALS Wohnfläche mit Streichfläche.
  Bei Standardraumhöhe (~2.5 m): Wandfläche ≈ 2.4 × Wohnfläche (Türen/Fenster abgezogen).
  Decke ≈ Wohnfläche.
  Streichfläche gesamt ≈ 3.4 × Wohnfläche, wenn Decken mit gestrichen werden.

INPUT-TREUE (KRITISCH):
- Wenn der Kunde explizit eine Endmenge angibt (z.B. "17 m² Holzfläche gesamt", "240 m² Fassade",
  "175 m² Wandfläche"), MUSST du genau diesen Wert übernehmen.
- Rechne NICHT selbst nach (z.B. 12 Stück × 1.2 m × 0.6 m = 8.64 m²) wenn die Gesamtsumme bereits genannt wurde.
- Eigene Berechnungen sind nur dann erlaubt, wenn KEINE Endmenge geliefert wurde.

PREIS-FAUSTREGELN (€/m² sind GESAMTPREISE inkl. Lohn UND Material UND Vorarbeiten — NICHT additiv kombinieren!):
- Innenraum-Streichen Standard (Wand+Decke, Lohn+Material+Standard-Vorarbeiten): 8–15 €/m² Streichfläche.
- Innenraum mit umfangreichen Vorarbeiten (Spachteln, Tapete entfernen, Schimmelsanierung): 25–40 €/m² als Gesamttarif.
- Fassade Standard (Lohn+Material, OHNE Gerüst): 25–45 €/m² als Gesamttarif.
- Gerüst Einfamilienhaus (~200–300 m² Fassade, 2 Wochen Standzeit): 1500–3000 € pauschal (separate Position).

WICHTIG zur Tarif-Anwendung:
- Wähle EIN Tarifband pro Leistungsbereich (Innen oder Außen).
- Vorarbeiten sind im €/m²-Tarif bereits ENTHALTEN — füge KEINE separate "Vorarbeiten X m² × Y €/m²"-Zeile zusätzlich zum Streich-Tarif hinzu.
- Wenn du Vorarbeiten als eigene Position ausweisen willst: nutze entweder Pauschale (z.B. 200-500 € für Standard-Vorarbeiten) ODER Stunden-Position (Std × Stundensatz), NICHT noch ein €/m²-Tarif obendrauf.

LOHN-FAUSTREGELN (für Stunden-basierte Positionen):
- Innenraum-Streichen Standard: 1 Maler schafft 5–7 m² Streichfläche pro Stunde.
- Innenraum mit umfangreichen Vorarbeiten: 3–4 m²/h.
- Fassade Standard (mit Gerüst gestellt): 4–5 m²/h.
- Stundensätze DE 2026: 50–65 €/h netto (Standard), 65–80 €/h komplexe Spezialarbeit.

UNSICHERHEIT:
- Wenn Mengenangaben fehlen: Faustregeln + Mitte des Bereichs anwenden, Annahme im 'notes'-Feld vermerken."""

    _MATERIAL_USAGE_RULES = """MATERIAL-VERBRAUCH (Faustregeln für Mengenkalkulation):
- Dispersionsfarbe Innen: 1 L deckt ~5–7 m² (1 Anstrich). Bei 2 Anstrichen Verbrauch verdoppeln.
- Silikatfarbe Fassade: 1 L deckt ~4–6 m² (typisch 2 Anstriche).
- Tiefgrund / Isoliergrund: 1 L deckt ~6–8 m².
- Spachtelmasse für Risse: ca. 1 kg pro 3–5 m Wandlänge mit Rissen.
- Kalkuliere Materialmengen IMMER aus der Streichfläche und diesen Faustregeln, nicht aus Bauchgefühl."""

    def __init__(self):
        api_key = settings.openai_api_key
        if api_key and api_key != 'test_key_placeholder' and api_key.startswith('sk-'):
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = settings.openai_model
            self.vision_model = settings.openai_vision_model
            self.embedding_model = settings.openai_embedding_model
            self.enabled = True
            logger.info(
                "OpenAI client initialized (text=%s, vision=%s, embedding=%s)",
                self.model, self.vision_model, self.embedding_model,
            )
        else:
            self.client = None
            self.model = None
            self.vision_model = None
            self.embedding_model = None
            self.enabled = False
            logger.warning("OpenAI API key not configured, using mock responses")

    def _raise_if_strict(self, exc: Exception) -> None:
        """In strict mode (settings.ai_strict_mode), surface AI errors instead
        of silently falling back to static mock data. Used by tests and
        iteration scripts so broken prompts / invalid keys don't get masked.
        """
        if settings.ai_strict_mode:
            raise exc

    async def visual_estimate(self, image_b64: str, mime_type: str,
                              extra_context: Optional[str] = None) -> Dict:
        """Phase 1: On-site photo analysis using the dedicated vision model.

        Returns a structured estimate of the surface area, substrate condition,
        visible prep work and risk factors — the raw material for a fast quote
        from a single photo taken by the contractor on site.
        """
        if not self.enabled:
            return self._get_mock_visual_estimate()

        system_prompt = """Du bist ein erfahrener Malermeister in Deutschland mit 20 Jahren Berufserfahrung.
Der Handwerker schickt dir ein Foto von einer Baustelle und du musst daraus
alle relevanten Informationen für einen Kostenvoranschlag extrahieren.

Analysiere das Foto SORGFÄLTIG und schätze:
- Raumtyp (Wohnzimmer, Bad, Flur, Fassade außen, Treppenhaus, etc.)
- Grobe Flächenschätzung in Quadratmetern (Wände, Decke separat wenn erkennbar)
- Aktueller Zustand des Untergrunds (neu, gut, Risse, Schimmel, Tapete, alte Farbe, etc.)
- Notwendige Vorarbeiten (Spachteln, Grundierung, Tapete entfernen, Schimmelsanierung)
- Sichtbare Risiken oder Besonderheiten (hohe Decke, Stuck, empfindliche Böden, Möbel)
- Empfohlene Materialqualität (Standard-Dispersion, Premium-Silikat, etc.)
- Geschätzte Arbeitszeit in Stunden

WICHTIG: Wenn die Flächenschätzung unsicher ist, gib einen Bereich an (z.B. 20-30m²).
Antworte AUSSCHLIESSLICH im folgenden JSON-Schema (kein Markdown):
{
  "room_type": "string",
  "estimated_area_sqm": {"wall": number, "ceiling": number, "total": number},
  "area_confidence": "low|medium|high",
  "substrate_condition": "string",
  "required_prep_work": ["string"],
  "risk_factors": ["string"],
  "recommended_material_quality": "standard|premium|special",
  "estimated_labor_hours": number,
  "summary": "string (2-3 Sätze)"
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (extra_context or "Bitte analysiere dieses Foto der Baustelle für einen Kostenvoranschlag."),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            },
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=messages,
                temperature=0.2,
                max_tokens=900,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Vision estimate returned invalid JSON: %s", content)
            self._raise_if_strict(e)
            return self._get_mock_visual_estimate()
        except Exception as e:
            logger.error("Vision estimate error: %s", e)
            self._raise_if_strict(e)
            return self._get_mock_visual_estimate()

    def _get_mock_visual_estimate(self) -> Dict:
        """Offline / no-API fallback for the visual estimate endpoint."""
        return {
            "room_type": "Wohnzimmer",
            "estimated_area_sqm": {"wall": 42.0, "ceiling": 22.0, "total": 64.0},
            "area_confidence": "medium",
            "substrate_condition": "Bestehende Dispersionsfarbe, leichte Risse im oberen Wandbereich",
            "required_prep_work": [
                "Risse spachteln und schleifen",
                "Grundierung auf Reparaturstellen",
                "Abkleben von Fenstern und Steckdosen",
            ],
            "risk_factors": [
                "Deckenhöhe über 2,70 m (Gerüst/Leiter)",
                "Empfindlicher Parkettboden — sorgfältig abdecken",
            ],
            "recommended_material_quality": "standard",
            "estimated_labor_hours": 14.0,
            "summary": (
                "Standard-Wohnraum mit solidem Untergrund. Vor dem Anstrich sind "
                "kleinere Spachtelarbeiten an den Wänden nötig. Geschätzte "
                "Gesamtfläche ca. 64m² inkl. Decke."
            ),
        }

    async def create_embedding(self, text: str) -> List[float]:
        """Create an OpenAI embedding for RAG material retrieval.

        Returns a zero-vector of the configured dimension when the API is not
        available, so downstream similarity search degrades gracefully.
        """
        if not self.enabled:
            return [0.0] * settings.openai_embedding_dimension
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Embedding error for text %.60r: %s", text, e)
            return [0.0] * settings.openai_embedding_dimension

    async def analyze_project_description(self, description: str, context: str = "initial_input", conversation_history: Optional[List[Dict]] = None) -> Dict:
        """Analyze project description and generate intelligent follow-up questions"""
        
        if not self.enabled:
            return self._get_mock_analysis_response(description)
        
        try:
            system_prompt = """Du bist ein erfahrener Maler-Experte und KI-Assistent für Kostenvoranschläge. 
            Deine Aufgabe ist es, Projektbeschreibungen zu analysieren und intelligente Rückfragen zu stellen, 
            um alle notwendigen Informationen für einen präzisen Kostenvoranschlag zu sammeln.

            Analysiere die Projektbeschreibung und generiere 2-4 relevante Rückfragen als Multiple-Choice oder 
            offene Fragen. Fokussiere dich auf:
            - Fehlende technische Details (Fläche, Höhe, Zustand)
            - Materialwünsche und Qualität
            - Zeitrahmen und Zugänglichkeit
            - Vorarbeiten und Besonderheiten

            Antworte im JSON-Format:
            {
                "analysis": {
                    "project_type": "string",
                    "estimated_area": "number or null",
                    "complexity": "low|medium|high",
                    "missing_info": ["list of missing information"]
                },
                "questions": [
                    {
                        "id": "unique_id",
                        "question": "Frage-Text",
                        "type": "multiple_choice|text|number",
                        "options": ["option1", "option2"] // nur bei multiple_choice
                    }
                ],
                "suggestions": ["hilfreiche Tipps für den Kunden"]
            }"""

            # Build conversation context
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages for context
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            messages.append({
                "role": "user",
                "content": f"""Projektbeschreibung: {description}

                Kontext: {context}
                
                Bitte analysiere diese Beschreibung und stelle intelligente Rückfragen."""
            })

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )

            content = response.choices[0].message.content
            
            # Parse JSON response
            try:
                # remove '''json ''' from content
                content = content.replace('```json', '').replace('```', '')
                result = json.loads(content)
                return result
            except json.JSONDecodeError as je:
                logger.error(f"Failed to parse OpenAI JSON response: {content}")
                self._raise_if_strict(je)
                return self._get_mock_analysis_response(description)

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            self._raise_if_strict(e)
            return self._get_mock_analysis_response(description)

    async def process_answers_and_generate_quote(self,
                                                project_data: Dict,
                                                answers: List[Dict],
                                                conversation_history: Optional[List[Dict]] = None,
                                                document_files: Optional[List[Dict]] = None,
                                                hourly_rate: Optional[float] = None,
                                                material_cost_markup: Optional[float] = None,
                                                material_context: Optional[List[Dict]] = None) -> Dict:
        """Process user answers and generate a detailed quote, including multimodal document files as base64.

        If ``material_context`` is provided (Phase 2 RAG), the retrieved real-world
        prices are injected into the system prompt so the LLM grounds its cost
        estimates in actual data rather than guessing.
        """

        if not self.enabled:
            return self._get_mock_quote_response(project_data, answers)

        try:
            system_prompt = f"""Du bist ein erfahrener Maler-Meister und erstellst präzise Kostenvoranschläge.
            Basierend auf der Projektbeschreibung, den Antworten des Kunden und den angehängten Dokumenten (Pläne, Fotos), identifiziere die einzelnen Positionen für einen detaillierten Kostenvoranschlag.

            {self._build_cost_instructions(hourly_rate, material_cost_markup)}

            {self._build_material_context_block(material_context)}

            {self._PLAUSIBILITY_RULES}

            {self._MATERIAL_USAGE_RULES}

            Berücksichtige außerdem:
            - Schwierigkeitsgrad und Zugänglichkeit
            - Regionale Preisunterschiede (Deutschland)
            - Die Inhalte und Hinweise aus den hochgeladenen Dokumenten

            DEINE AUFGABE: Liste der Positionen identifizieren. Du musst NICHT subtotal, MwSt oder total_amount ausrechnen — das macht ein deterministischer Calculator danach.
            - Pro Position: description, quantity, unit, unit_price (NETTO), category. total_price wird automatisch berechnet als quantity × unit_price.
            - Lohn-Positionen NUR ALS EINS von beiden ausweisen: entweder als Stunden-Position (unit="h", unit_price=Stundensatz) ODER als €/m²-Pauschal-Position (unit="m²", unit_price=€/m²-Tarif). NIEMALS beides für dieselbe Leistung.

            Antworte im JSON-Format:
            {{
                "project_title": "string",
                "items": [
                    {{
                        "description": "string",
                        "quantity": number,
                        "unit": "string (m²|h|L|Stk|pauschal)",
                        "unit_price": number,
                        "category": "labor|material|additional"
                    }}
                ],
                "notes": "string",
                "recommendations": ["string"]
            }}"""

            # Build conversation context
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages for context
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Haupt-User-Message mit Projektdaten und Antworten
            user_content = [
                {"type": "text", "text": f"Projektdaten:\n{json.dumps(project_data, indent=2, ensure_ascii=False)}\n\nKundenantworten:\n{json.dumps(answers, indent=2, ensure_ascii=False)}\n\nErstelle einen detaillierten Kostenvoranschlag."}
            ]
            # Multimodale Dokumente als image_url/base64 anhängen
            if document_files:
                for doc in document_files:
                    if doc.get("base64") and doc.get("mime_type"):
                        user_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{doc['mime_type']};base64,{doc['base64']}"
                            }
                        })
            messages.append({
                "role": "user",
                "content": user_content
            })

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2000
            )

            content = response.choices[0].message.content

            try:
                # gpt-4o-mini sometimes wraps JSON in ```json ... ``` fences
                # despite instructions; strip them to keep the parser robust.
                if content.strip().startswith("```"):
                    lines = content.strip().split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    content = "\n".join(lines)
                llm_result = json.loads(content)
                project_text = " ".join([
                    str(project_data.get("description", "")),
                    str(project_data.get("additional_info", "")),
                ])
                return self._finalize_quote_with_calculator(
                    llm_result=llm_result,
                    project_text=project_text,
                    hourly_rate=hourly_rate,
                )
            except json.JSONDecodeError as je:
                logger.error(f"Failed to parse OpenAI quote JSON: {content}")
                self._raise_if_strict(je)
                return self._get_mock_quote_response(project_data, answers)

        except Exception as e:
            logger.error(f"OpenAI API error in quote generation: {str(e)}")
            self._raise_if_strict(e)
            return self._get_mock_quote_response(project_data, answers)

    def _finalize_quote_with_calculator(
        self,
        llm_result: Dict,
        project_text: str,
        hourly_rate: Optional[float] = None,
    ) -> Dict:
        """Run LLM-identified positions through the deterministic calculator,
        then reshape into the legacy `{quote: {...}, items: [...]}` envelope
        so routes/ai.py and the QuickQuoteResponse schema keep working.

        The calculator owns: total_price normalization, subtotal, VAT, totals,
        plausibility warnings (merged into notes).
        """
        items_in = llm_result.get("items", []) or []
        project_type = quote_calculator.detect_project_type(project_text)
        calc = quote_calculator.calculate(items_in, project_type=project_type)

        # Reattach position numbers & ensure unit defaults — needed by Quote
        # and QuickQuoteResponse downstream.
        items_out = []
        for idx, item in enumerate(calc.items, start=1):
            item.setdefault("position", idx)
            item.setdefault("unit", "Stk")
            item.setdefault("category", item.get("category", "labor"))
            items_out.append(item)

        labor_hours = sum(
            float(i.get("quantity", 0) or 0)
            for i in items_out
            if (i.get("unit") or "").lower() in {"h", "std", "stunde", "stunden"}
            and (i.get("category") or "").lower() == "labor"
        )
        material_cost = sum(
            float(i.get("total_price", 0) or 0)
            for i in items_out
            if (i.get("category") or "").lower() == "material"
        )

        notes = llm_result.get("notes", "") or ""
        if calc.warnings:
            warnings_block = "Plausibilitätshinweise: " + " | ".join(calc.warnings)
            notes = f"{notes}\n\n{warnings_block}".strip() if notes else warnings_block

        return {
            "quote": {
                "project_title": llm_result.get("project_title", "Malerarbeiten"),
                "subtotal": calc.subtotal,
                "vat_amount": calc.vat_amount,
                "total_amount": calc.total_amount,
                "labor_hours": labor_hours,
                "hourly_rate": hourly_rate or 0,
                "material_cost": round(material_cost, 2),
                "additional_costs": 0,
            },
            "items": items_out,
            "notes": notes,
            "recommendations": llm_result.get("recommendations", []),
        }

    async def generate_quick_quote(self, service_description: str, area: Optional[str] = None,
                                   additional_info: Optional[str] = None,
                                   hourly_rate: Optional[float] = None,
                                   material_cost_markup: Optional[float] = None) -> Dict:
        """Generate a quote in a single GPT call from minimal input (MVP Quick Quote)."""

        if not self.enabled:
            return self._get_mock_quick_quote_response(service_description)

        try:
            system_prompt = f"""Du bist ein erfahrener Malermeister in Deutschland.
Erstelle einen professionellen Kostenvoranschlag basierend auf der Beschreibung des Kunden.

{self._build_cost_instructions(hourly_rate, material_cost_markup)}

{self._PLAUSIBILITY_RULES}

{self._MATERIAL_USAGE_RULES}

DEINE AUFGABE: Liste der Positionen identifizieren. Du musst NICHT subtotal, MwSt oder total_amount ausrechnen — das macht ein deterministischer Calculator danach.
- Pro Position: description, quantity, unit, unit_price (NETTO), category. total_price wird automatisch berechnet als quantity × unit_price.
- Material (Farbe, Grundierung, Abdeckmaterial) als separate Positionen mit category="material".
- Vorarbeiten als eigene Position (entweder pauschal oder als Stunden), category="preparation" oder "labor".
- Lohn-Positionen NUR ALS EINS von beiden ausweisen: entweder als Stunden-Position (unit="h", unit_price=Stundensatz) ODER als €/m²-Pauschal-Position (unit="m²", unit_price=€/m²-Tarif). NIEMALS beides für dieselbe Leistung.
- Bei fehlenden Flächenangaben den Plausibilitätsregeln folgen und Annahmen im 'notes'-Feld benennen.

Antworte AUSSCHLIESSLICH im folgenden JSON-Format (kein Markdown, keine Erklärungen drumherum):
{{
  "project_title": "Kurzer Projekttitel",
  "items": [
    {{"description": "Beschreibung der Position", "quantity": 1.0, "unit": "m²", "unit_price": 10.00, "category": "labor"}}
  ],
  "notes": "Hinweise zum Angebot",
  "recommendations": ["Empfehlung 1"]
}}"""

            user_input = f"Leistung: {service_description}"
            if area:
                user_input += f"\nFläche/Umfang: {area}"
            if additional_info:
                user_input += f"\nZusatzinfo: {additional_info}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2000
            )

            content = response.choices[0].message.content

            # Strip markdown code fences if present
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines)

            llm_result = json.loads(content)
            project_text = " ".join(filter(None, [service_description, area, additional_info]))
            project_type = quote_calculator.detect_project_type(project_text)
            calc = quote_calculator.calculate(llm_result.get("items", []), project_type=project_type)

            items_out = []
            for idx, item in enumerate(calc.items, start=1):
                item.setdefault("position", idx)
                item.setdefault("unit", "Stk")
                item.setdefault("category", item.get("category", "labor"))
                items_out.append(item)

            notes = llm_result.get("notes", "") or ""
            if calc.warnings:
                warnings_block = "Plausibilitätshinweise: " + " | ".join(calc.warnings)
                notes = f"{notes}\n\n{warnings_block}".strip() if notes else warnings_block

            return {
                "project_title": llm_result.get("project_title", "Malerarbeiten"),
                "items": items_out,
                "subtotal": calc.subtotal,
                "vat_amount": calc.vat_amount,
                "total_amount": calc.total_amount,
                "notes": notes,
                "recommendations": llm_result.get("recommendations", []),
            }

        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse quick quote JSON: {content}")
            self._raise_if_strict(je)
            return self._get_mock_quick_quote_response(service_description)
        except Exception as e:
            logger.error(f"OpenAI API error in quick quote: {str(e)}")
            self._raise_if_strict(e)
            return self._get_mock_quick_quote_response(service_description)

    def _get_mock_quick_quote_response(self, service_description: str) -> Dict:
        """Mock response for quick quote when OpenAI is not available."""
        return {
            "project_title": f"Malerarbeiten - {service_description[:50]}",
            "items": [
                {"position": 1, "description": "Vorarbeiten: Abkleben und Abdecken", "quantity": 1.0, "unit": "pauschal", "unit_price": 120.00, "total_price": 120.00, "category": "preparation"},
                {"position": 2, "description": "Grundierung der Wandflächen", "quantity": 40.0, "unit": "m²", "unit_price": 4.50, "total_price": 180.00, "category": "material"},
                {"position": 3, "description": "Wandanstrich 2x Dispersionsfarbe weiß", "quantity": 40.0, "unit": "m²", "unit_price": 8.50, "total_price": 340.00, "category": "labor"},
                {"position": 4, "description": "Material: Dispersionsfarbe, Grundierung, Kleinmaterial", "quantity": 1.0, "unit": "pauschal", "unit_price": 185.00, "total_price": 185.00, "category": "material"}
            ],
            "subtotal": 825.00,
            "vat_amount": 156.75,
            "total_amount": 981.75,
            "notes": "Dies ist ein Muster-Kostenvoranschlag. Die tatsächlichen Preise können je nach Objektbesichtigung abweichen.",
            "recommendations": [
                "Eine Vor-Ort-Besichtigung wird empfohlen für ein verbindliches Angebot.",
                "Hochwertige Markenfarben sorgen für bessere Deckkraft und längere Haltbarkeit."
            ]
        }

    async def ask_follow_up_question_stream(self, conversation_history: List[Dict], 
                                          user_message: str):
        """Handle follow-up questions with streaming response and intelligent questions"""
        
        if not self.enabled:
            # Stream mock response
            mock_response = self._get_mock_followup_response(user_message)
            response_text = mock_response.get("response", "")
            
            # Stream the response character by character for realistic effect
            for char in response_text:
                yield {
                    "type": "content",
                    "content": char
                }
                await asyncio.sleep(0.01)  # Small delay for streaming effect
            
            # After streaming text, yield intelligent questions if available
            intelligent_followup = self._get_mock_intelligent_followup(user_message)
            if intelligent_followup.get("has_follow_up_questions"):
                yield {
                    "type": "intelligent_questions",
                    "questions": intelligent_followup.get("questions", []),
                    "completion_status": intelligent_followup.get("completion_status", {}),
                    "suggestions": intelligent_followup.get("suggestions", [])
                }
            
            yield {"type": "done"}
            return
        
        try:
            # First, stream the natural response
            system_prompt = """Du bist ein hilfsreicher KI-Assistent für Maler-Kostenvoranschläge.
            Beantworte Fragen des Kunden höflich und kompetent. Sei freundlich und professionell.
            
            Antworte direkt und natürlich, ohne JSON-Formatierung oder zusätzliche Fragen in diesem Teil."""

            # Build conversation context
            messages = [{"role": "system", "content": system_prompt}]
            
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            messages.append({"role": "user", "content": user_message})

            # Stream the natural response first
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=600,
                stream=True
            )

            full_response = ""
            async for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield {
                        "type": "content",
                        "content": content
                    }
            
            # After streaming the response, generate intelligent follow-up questions
            try:
                # Update conversation history with the response for context
                updated_history = conversation_history + [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": full_response}
                ]
                
                intelligent_followup = await self.ask_intelligent_follow_up(
                    updated_history, 
                    user_message
                )
                
                # Stream intelligent questions if available
                if intelligent_followup.get("has_follow_up_questions"):
                    yield {
                        "type": "intelligent_questions",
                        "questions": intelligent_followup.get("questions", []),
                        "completion_status": intelligent_followup.get("completion_status", {}),
                        "suggestions": intelligent_followup.get("suggestions", [])
                    }
                
            except Exception as followup_error:
                logger.warning(f"Error generating intelligent follow-up in stream: {followup_error}")
                # Continue without follow-up questions
            
            yield {"type": "done"}

        except Exception as e:
            logger.error(f"OpenAI streaming error in follow-up: {str(e)}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def ask_intelligent_follow_up(self, conversation_history: List[Dict], 
                                      user_message: str,
                                      context: Dict = None) -> Dict:
        """Generate intelligent context-aware follow-up questions"""
        
        if not self.enabled:
            return self._get_mock_intelligent_followup(user_message, context)
        
        try:
            # Analyze conversation for missing information
            missing_info = await self._analyze_missing_information(conversation_history)
            
            system_prompt = """Du bist ein erfahrener Maler-Experte und KI-Assistent für Kostenvoranschläge.
            Deine Aufgabe ist es, intelligente und kontextbezogene Nachfragen zu stellen, um alle notwendigen 
            Informationen für einen präzisen Kostenvoranschlag zu sammeln.
            
            Analysiere den bisherigen Gesprächsverlauf und die aktuelle Nachricht des Kunden.
            Stelle nur dann Nachfragen, wenn wichtige Informationen fehlen oder unklar sind.
            
            WICHTIGE REGELN:
            1. Stelle maximal 2-3 gezielte Fragen pro Antwort
            2. Priorisiere die wichtigsten fehlenden Informationen
            3. Berücksichtige bereits gegebene Antworten
            4. Verwende natürliche, freundliche Sprache
            5. Biete Multiple-Choice-Optionen für komplexe Fragen an
            
            Fokussiere dich auf:
            - Fehlende Flächenangaben (Quadratmeter, Raumanzahl)
            - Materialwünsche (Farbtyp, Qualität)
            - Oberflächenzustand (Vorarbeiten nötig?)
            - Zeitrahmen und Terminwünsche
            - Besondere Anforderungen oder Herausforderungen
            
            Antworte im JSON-Format:
            {
                "response": "Natürliche Antwort auf die Kundennachricht",
                "has_follow_up_questions": boolean,
                "questions": [
                    {
                        "id": "unique_id",
                        "question": "Konkrete Frage",
                        "type": "multiple_choice|text|number|yes_no",
                        "importance": "high|medium|low",
                        "options": ["option1", "option2"] // nur bei multiple_choice
                    }
                ],
                "completion_status": {
                    "estimated_completeness": number, // 0-100%
                    "missing_critical_info": ["info1", "info2"],
                    "ready_for_quote": boolean
                },
                "suggestions": ["Hilfreiche Tipps für den Kunden"]
            }"""

            # Build conversation context with missing info analysis
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add context about missing information
            if missing_info:
                messages.append({
                    "role": "system", 
                    "content": f"Fehlende Informationen aus der Analyse: {json.dumps(missing_info, ensure_ascii=False)}"
                })
            
            # Add conversation history
            for msg in conversation_history[-8:]:  # More context for better analysis
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            # Add current message with additional context
            context_info = ""
            if context:
                context_info = f"\n\nZusätzlicher Kontext: {json.dumps(context, ensure_ascii=False)}"
            
            messages.append({
                "role": "user", 
                "content": f"{user_message}{context_info}"
            })

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.6,  # Slightly lower for more consistent questions
                max_tokens=1200
            )

            content = response.choices[0].message.content
            
            try:
                # Clean JSON from markdown formatting
                content = content.replace('```json', '').replace('```', '').strip()
                result = json.loads(content)
                
                # Ensure all required fields exist
                result.setdefault('has_follow_up_questions', False)
                result.setdefault('questions', [])
                result.setdefault('completion_status', {
                    'estimated_completeness': 50,
                    'missing_critical_info': [],
                    'ready_for_quote': False
                })
                result.setdefault('suggestions', [])
                
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse intelligent follow-up JSON: {content}")
                return self._get_mock_intelligent_followup(user_message, context)

        except Exception as e:
            logger.error(f"OpenAI API error in intelligent follow-up: {str(e)}")
            return self._get_mock_intelligent_followup(user_message, context)
    
    async def _analyze_missing_information(self, conversation_history: List[Dict]) -> Dict:
        """Analyze conversation to identify missing critical information"""
        
        # Define critical information categories for painting quotes
        required_info = {
            "area_info": ["Quadratmeter", "Raumanzahl", "Deckenhöhe"],
            "surface_info": ["Wandzustand", "Vorarbeiten", "Untergrund"],
            "material_info": ["Farbwunsch", "Qualität", "Spezialanforderungen"],
            "timeline_info": ["Zeitrahmen", "Terminwünsche"],
            "access_info": ["Zugänglichkeit", "Möbel räumen", "Arbeitszeiten"]
        }
        
        missing_categories = []
        found_info = {}
        
        # Analyze conversation content for mentioned information
        full_conversation = " ".join([msg.get("content", "").lower() for msg in conversation_history])
        
        for category, keywords in required_info.items():
            found_keywords = []
            for keyword in keywords:
                # Simple keyword matching (could be enhanced with NLP)
                if any(term in full_conversation for term in [
                    keyword.lower(), 
                    keyword.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").lower()
                ]):
                    found_keywords.append(keyword)
            
            if found_keywords:
                found_info[category] = found_keywords
            else:
                missing_categories.append(category)
        
        return {
            "missing_categories": missing_categories,
            "found_info": found_info,
            "completeness_score": max(0, 100 - (len(missing_categories) * 20))
        }
    
    async def ask_follow_up_question(self, conversation_history: List[Dict], 
                                   user_message: str) -> Dict:
        """Handle follow-up questions in the conversation (legacy method)"""
        
        # Use the new intelligent follow-up method
        return await self.ask_intelligent_follow_up(conversation_history, user_message)
    
    def _get_mock_intelligent_followup(self, message: str, context: Dict = None) -> Dict:
        """Enhanced mock response for intelligent follow-up questions"""
        return {
            "response": "Vielen Dank für die zusätzlichen Informationen! Um Ihnen einen möglichst genauen Kostenvoranschlag erstellen zu können, habe ich noch ein paar spezifische Fragen.",
            "has_follow_up_questions": True,
            "questions": [
                {
                    "id": "room_size",
                    "question": "Wie groß ist der zu streichende Bereich ungefähr?",
                    "type": "multiple_choice",
                    "importance": "high",
                    "options": ["Unter 20 m²", "20-40 m²", "40-80 m²", "Über 80 m²"]
                },
                {
                    "id": "wall_condition",
                    "question": "Wie ist der aktuelle Zustand der Wände?",
                    "type": "multiple_choice",
                    "importance": "high",
                    "options": ["Neu/sehr gut", "Kleine Risse/Löcher", "Größere Schäden", "Unsicher"]
                },
                {
                    "id": "timeline",
                    "question": "Bis wann soll das Projekt abgeschlossen sein?",
                    "type": "text",
                    "importance": "medium"
                }
            ],
            "completion_status": {
                "estimated_completeness": 60,
                "missing_critical_info": ["Flächenangabe", "Oberflächenzustand"],
                "ready_for_quote": False
            },
            "suggestions": [
                "Fotos der zu streichenden Räume können bei der Kostenschätzung helfen",
                "Bei größeren Schäden an den Wänden können zusätzliche Vorarbeiten nötig sein"
            ]
        }

    async def analyze_document(self, file_content: bytes, filename: str, content_type: str) -> Dict:
        """Analyze uploaded document (floor plan, photo) using AI"""
        
        if not self.enabled:
            return self._get_mock_document_analysis()
        
        try:
            # Convert file content to base64
            base64_content = base64.b64encode(file_content).decode('utf-8')
            
            system_prompt = """Du bist ein Experte für die Analyse von Grundrissen und Fotos von Räumen.
            Analysiere das Bild und extrahiere relevante Informationen für einen Maler-Kostenvoranschlag.

            Antworte im JSON-Format:
            {
                "extracted_text": "string",
                "detected_rooms": ["string"],
                "estimated_area": number,
                "notes": "string",
                "recommendations": ["string"]
            }"""

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Bitte analysiere dieses Bild ({filename}) für einen Maler-Kostenvoranschlag."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_content}"
                            }
                        }
                    ]
                }
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )

            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse OpenAI document analysis JSON: {content}")
                return self._get_mock_document_analysis()

        except Exception as e:
            logger.error(f"OpenAI API error in document analysis: {str(e)}")
            return self._get_mock_document_analysis()

    def _build_material_context_block(self, material_context: Optional[List[Dict]] = None) -> str:
        """Format retrieved material prices as a grounded-context block for the LLM.

        Returns an empty string when no context is supplied so the prompt stays
        compact for free-tier / RAG-disabled requests.
        """
        if not material_context:
            return ""
        lines = ["REALE MATERIALPREISE (aus Produktdatenbank — NUTZE DIESE als Grundlage):"]
        for m in material_context[:10]:
            name = m.get("name", "")
            manufacturer = m.get("manufacturer") or "—"
            unit = m.get("unit") or "Stk"
            price = m.get("price_net")
            region = m.get("region") or "DE"
            lines.append(
                f"- {name} ({manufacturer}): {price:.2f} EUR/{unit} netto, Region {region}"
                if price is not None
                else f"- {name} ({manufacturer}): Preis n/a, Einheit {unit}, Region {region}"
            )
        return "\n".join(lines)

    def _build_cost_instructions(self, hourly_rate: Optional[float] = None,
                                   material_cost_markup: Optional[float] = None) -> str:
        """Build cost parameter instructions for AI prompts based on user settings."""
        rate = (f"- Verwende einen Stundensatz von {hourly_rate:.2f} EUR/h netto für alle Arbeitszeit-Positionen."
                if hourly_rate is not None
                else "- Arbeitszeit realistisch kalkulieren (Stundensatz 45-55 EUR/h netto)")
        markup = (f"- Auf die Netto-Materialkosten einen Aufschlag von {material_cost_markup:.1f}% berechnen."
                  if material_cost_markup is not None
                  else "- Materialkosten (Farbe, Grundierung, Werkzeug) zu marktüblichen Preisen kalkulieren")
        return f"KOSTENPARAMETER:\n{rate}\n{markup}"

    def _get_mock_analysis_response(self, description: str) -> Dict:
        """Mock response for testing without OpenAI API"""
        return {
            "analysis": {
                "project_type": "Innenraumstreichung",
                "estimated_area": 25,
                "complexity": "medium",
                "missing_info": ["Genaue Quadratmeter", "Farbwunsch", "Vorarbeiten"]
            },
            "questions": [
                {
                    "id": "area_size",
                    "question": "Wie groß ist die zu streichende Fläche in Quadratmetern?",
                    "type": "multiple_choice",
                    "options": ["Unter 20m²", "20-40m²", "40-60m²", "Über 60m²"]
                },
                {
                    "id": "paint_type",
                    "question": "Welche Art von Farbe soll verwendet werden?",
                    "type": "multiple_choice",
                    "options": ["Standard-Wandfarbe", "Premium-Farbe", "Spezialfarbe", "Kundenwunsch"]
                },
                {
                    "id": "prep_work",
                    "question": "Sind Vorarbeiten nötig (z.B. Spachteln, Grundierung)?",
                    "type": "multiple_choice",
                    "options": ["Ja, umfangreich", "Ja, minimal", "Nein", "Unsicher"]
                }
            ],
            "suggestions": [
                "Vielen Dank für die Information. Können Sie mir noch sagen, ob spezielle Vorbereitungen nötig sind?",
                "Kleinere Ausbesserungen können den Preis beeinflussen."
            ]
        }

    def _get_mock_quote_response(self, project_data: Dict, answers: List[Dict]) -> Dict:
        """Mock response for quote generation without OpenAI API"""
        return {
            "quote": {
                "project_title": "Wohnzimmer streichen",
                "total_amount": 1250.00,
                "labor_hours": 16.0,
                "hourly_rate": 45.00,
                "material_cost": 530.00,
                "additional_costs": 0.00
            },
            "items": [
                {
                    "description": "Wandflächen grundieren und streichen",
                    "quantity": 25.5,
                    "unit": "m²",
                    "unit_price": 15.00,
                    "total_price": 382.50,
                    "category": "labor"
                },
                {
                    "description": "Premium-Wandfarbe",
                    "quantity": 2,
                    "unit": "Eimer",
                    "unit_price": 45.00,
                    "total_price": 90.00,
                    "category": "material"
                }
            ],
            "notes": "Preis inkl. MwSt. Material wird gestellt.",
            "recommendations": [
                "Möbel sollten vor Arbeitsbeginn ausgeräumt werden",
                "Für optimale Ergebnisse empfehlen wir eine Grundierung"
            ]
        }

    def _get_mock_followup_response(self, message: str) -> Dict:
        """Mock response for follow-up questions without OpenAI API (legacy)"""
        # Redirect to intelligent follow-up mock
        return self._get_mock_intelligent_followup(message)

    def _get_mock_document_analysis(self) -> Dict:
        """Mock response for document analysis without OpenAI API"""
        return {
            "extracted_text": "Wohnzimmer, 25m², 2.50m Deckenhöhe",
            "detected_rooms": ["Wohnzimmer"],
            "estimated_area": 25,
            "notes": "Grundriss zeigt rechteckigen Raum mit Fenster",
            "recommendations": [
                "Deckenhöhe berücksichtigen bei Materialberechnung",
                "Fensterbereich separat kalkulieren"
            ]
        }

    # === STREAMING METHODS FOR REAL-TIME RESPONSES ===
    
    async def ask_follow_up_question_stream(self, conversation_history: List[Dict], user_message: str):
        """Stream AI follow-up response in real-time"""
        
        if not self.enabled:
            # Mock streaming response
            async for chunk in self._get_mock_stream():
                yield chunk
            return
        
        try:
            system_prompt = """Du bist ein erfahrener Maler-Experte und hilfst bei Kostenvoranschlägen.
            Beantworte die Kundenfrage präzise und freundlich. Stelle bei Bedarf 1-2 gezielte Nachfragen
            für fehlende Informationen. Verwende natürliche, professionelle Sprache."""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation context (last 6 messages)
            for msg in conversation_history[-6:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Create streaming completion
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=800,
                stream=True
            )
            
            # Stream the response
            accumulated_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    accumulated_content += content
                    yield {
                        "type": "content",
                        "content": content
                    }
            
            # Send completion signal
            yield {
                "type": "done",
                "full_content": accumulated_content
            }
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def analyze_project_stream(self, description: str, context: str = "initial_input", 
                                   conversation_history: Optional[List[Dict]] = None):
        """Stream project analysis with intelligent questions"""
        
        if not self.enabled:
            # Mock streaming response
            async for chunk in self._get_mock_analysis_stream(description):
                yield chunk
            return
        
        try:
            system_prompt = """Du bist ein Maler-Experte und analysierst Projektbeschreibungen.
            Antworte strukturiert mit Analyse und 2-3 intelligenten Nachfragen.
            Format: Erst Analyse, dann Fragen mit Aufzählungszeichen."""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                for msg in conversation_history[-4:]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            messages.append({
                "role": "user",
                "content": f"Projektbeschreibung: {description}\n\nBitte analysiere und stelle Nachfragen."
            })
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                stream=True
            )
            
            accumulated_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    accumulated_content += content
                    yield {
                        "type": "content",
                        "content": content
                    }
            
            yield {
                "type": "done",
                "full_content": accumulated_content
            }
            
        except Exception as e:
            logger.error(f"Streaming analysis error: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _get_mock_stream(self):
        """Mock streaming for testing without OpenAI API"""
        response_text = """Vielen Dank für Ihre Anfrage! 

Basierend auf Ihrer Beschreibung kann ich bereits einige wichtige Punkte erfassen. 

Um Ihnen einen präzisen Kostenvoranschlag zu erstellen, benötige ich noch einige zusätzliche Informationen:

• Wie groß ist die zu streichende Fläche (in Quadratmetern)?
• Welche Farbwünsche haben Sie (Farbton, Qualität)?

Mit diesen Details kann ich Ihnen einen detaillierten Kostenvoranschlag erstellen."""
        
        # Simulate typing with small chunks
        words = response_text.split()
        current_chunk = ""
        
        for i, word in enumerate(words):
            current_chunk += word + " "
            
            # Send chunks every 2-3 words
            if (i + 1) % 3 == 0 or i == len(words) - 1:
                yield {
                    "type": "content", 
                    "content": current_chunk
                }
                current_chunk = ""
                await asyncio.sleep(0.05)  # Small delay for realistic typing
        
        yield {
            "type": "done",
            "full_content": response_text
        }
    
    async def _get_mock_analysis_stream(self, description: str):
        """Mock streaming analysis for testing"""
        response_text = f"""Projektanalyse für: "{description}"

**Erste Einschätzung:**
- Projekttyp: Innenanstrich
- Komplexität: Mittel
- Geschätzte Dauer: 1-2 Tage

**Nachfragen zur Präzisierung:**

• Welche Räume sollen gestrichen werden und wie groß sind diese?
• Ist eine Grundierung erforderlich oder nur der Deckanstrich?
• Haben Sie bereits Farbwünsche oder Materialvorstellungen?

Diese Informationen helfen mir, einen genauen Kostenvoranschlag zu erstellen."""
        
        # Stream in realistic chunks
        sentences = response_text.split('\n')
        
        for sentence in sentences:
            if sentence.strip():
                yield {
                    "type": "content",
                    "content": sentence + "\n"
                }
                await asyncio.sleep(0.1)
        
        yield {
            "type": "done", 
            "full_content": response_text
        }

