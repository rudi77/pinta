import os
import openai
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import base64

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and api_key != 'test_key_placeholder' and api_key.startswith('sk-'):
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = "gpt-4.1-mini"
            self.enabled = True
            logger.info("OpenAI client initialized successfully")
        else:
            self.client = None
            self.model = None
            self.enabled = False
            logger.warning("OpenAI API key not configured, using mock responses")

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
            except json.JSONDecodeError:
                logger.error(f"Failed to parse OpenAI JSON response: {content}")
                return self._get_mock_analysis_response(description)

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return self._get_mock_analysis_response(description)

    async def process_answers_and_generate_quote(self, 
                                                project_data: Dict, 
                                                answers: List[Dict],
                                                conversation_history: Optional[List[Dict]] = None,
                                                document_files: Optional[List[Dict]] = None) -> Dict:
        """Process user answers and generate a detailed quote, including multimodal document files as base64."""
        
        if not self.enabled:
            return self._get_mock_quote_response(project_data, answers)
        
        try:
            system_prompt = """Du bist ein erfahrener Maler-Meister und erstellst präzise Kostenvoranschläge.
            Basierend auf der Projektbeschreibung, den Antworten des Kunden und den angehängten Dokumenten (Pläne, Fotos), erstelle einen detaillierten Kostenvoranschlag mit realistischen Preisen für den deutschen Markt.

            Berücksichtige:
            - Materialkosten (Farbe, Grundierung, Werkzeug)
            - Arbeitszeit (Vorbereitung, Streichen, Nacharbeiten)
            - Schwierigkeitsgrad und Zugänglichkeit
            - Regionale Preisunterschiede (Deutschland)
            - Mehrwertsteuer (19%)
            - Die Inhalte und Hinweise aus den hochgeladenen Dokumenten

            Antworte im JSON-Format:
            {
                "quote": {
                    "project_title": "string",
                    "total_amount": number,
                    "labor_hours": number,
                    "hourly_rate": number,
                    "material_cost": number,
                    "additional_costs": number
                },
                "items": [
                    {
                        "description": "string",
                        "quantity": number,
                        "unit": "string",
                        "unit_price": number,
                        "total_price": number,
                        "category": "labor|material|additional"
                    }
                ],
                "notes": "string",
                "recommendations": ["string"]
            }"""

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
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse OpenAI quote JSON: {content}")
                return self._get_mock_quote_response(project_data, answers)

        except Exception as e:
            logger.error(f"OpenAI API error in quote generation: {str(e)}")
            return self._get_mock_quote_response(project_data, answers)

    async def ask_follow_up_question(self, conversation_history: List[Dict], 
                                   user_message: str) -> Dict:
        """Handle follow-up questions in the conversation"""
        
        if not self.enabled:
            return self._get_mock_followup_response(user_message)
        
        try:
            system_prompt = """Du bist ein hilfsreicher KI-Assistent für Maler-Kostenvoranschläge.
            Beantworte Fragen des Kunden höflich und kompetent. Wenn zusätzliche Informationen 
            benötigt werden, stelle gezielte Nachfragen.

            Antworte im JSON-Format:
            {
                "response": "string",
                "needs_more_info": boolean,
                "suggested_questions": ["string"] // optional
            }"""

            # Build conversation context
            messages = [{"role": "system", "content": system_prompt}]
            
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            messages.append({"role": "user", "content": user_message})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=800
            )

            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                # Fallback to simple text response
                return {
                    "response": content,
                    "needs_more_info": False,
                    "suggested_questions": []
                }

        except Exception as e:
            logger.error(f"OpenAI API error in follow-up: {str(e)}")
            return self._get_mock_followup_response(user_message)

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
        """Mock response for follow-up questions without OpenAI API"""
        return {
            "response": "Vielen Dank für Ihre Antwort. Können Sie mir noch sagen, ob es besondere Wünsche bezüglich der Farbqualität gibt?",
            "needs_more_info": True,
            "suggested_questions": [
                "Möchten Sie eine besonders hochwertige Farbe verwenden?",
                "Gibt es spezielle Anforderungen an die Haltbarkeit?"
            ]
        }

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

