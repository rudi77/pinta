import os
import openai
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and api_key != 'test_key_placeholder' and api_key.startswith('sk-'):
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = "gpt-4o"
            self.enabled = True
            logger.info("OpenAI client initialized successfully")
        else:
            self.client = None
            self.model = None
            self.enabled = False
            logger.warning("OpenAI API key not configured, using mock responses")

    async def analyze_project_description(self, description: str, context: str = "initial_input") -> Dict:
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

            user_prompt = f"""Projektbeschreibung: {description}

            Kontext: {context}
            
            Bitte analysiere diese Beschreibung und stelle intelligente Rückfragen."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )

            content = response.choices[0].message.content
            
            # Parse JSON response
            try:
                # remove '''json ''' from content
                content = content.replace('```json', '').replace('```', '')
                print(content)
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
                                                answers: List[Dict]) -> Dict:
        """Process user answers and generate a detailed quote"""
        
        if not self.enabled:
            return self._get_mock_quote_response(project_data, answers)
        
        try:
            system_prompt = """Du bist ein erfahrener Maler-Meister und erstellst präzise Kostenvoranschläge.
            Basierend auf der Projektbeschreibung und den Antworten des Kunden, erstelle einen detaillierten 
            Kostenvoranschlag mit realistischen Preisen für den deutschen Markt.

            Berücksichtige:
            - Materialkosten (Farbe, Grundierung, Werkzeug)
            - Arbeitszeit (Vorbereitung, Streichen, Nacharbeiten)
            - Schwierigkeitsgrad und Zugänglichkeit
            - Regionale Preisunterschiede (Deutschland)
            - Mehrwertsteuer (19%)

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

            user_prompt = f"""Projektdaten:
            {json.dumps(project_data, indent=2, ensure_ascii=False)}

            Kundenantworten:
            {json.dumps(answers, indent=2, ensure_ascii=False)}

            Erstelle einen detaillierten Kostenvoranschlag."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
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
        """Mock quote response for testing"""
        return {
            "quote": {
                "project_title": project_data.get("project_title", "Malerarbeiten"),
                "total_amount": 850.50,
                "labor_hours": 12,
                "hourly_rate": 45.0,
                "material_cost": 180.50,
                "additional_costs": 130.0
            },
            "items": [
                {
                    "description": "Wände und Decke streichen",
                    "quantity": 25,
                    "unit": "m²",
                    "unit_price": 18.0,
                    "total_price": 450.0,
                    "category": "labor"
                },
                {
                    "description": "Premium-Wandfarbe weiß",
                    "quantity": 3,
                    "unit": "Liter",
                    "unit_price": 35.0,
                    "total_price": 105.0,
                    "category": "material"
                },
                {
                    "description": "Grundierung und Spachtelmasse",
                    "quantity": 1,
                    "unit": "Pauschal",
                    "unit_price": 75.50,
                    "total_price": 75.50,
                    "category": "material"
                },
                {
                    "description": "Anfahrt und Entsorgung",
                    "quantity": 1,
                    "unit": "Pauschal",
                    "unit_price": 130.0,
                    "total_price": 130.0,
                    "category": "additional"
                }
            ],
            "notes": "Alle Preise inkl. 19% MwSt. Gültig für 30 Tage.",
            "recommendations": [
                "Empfehlung: Premium-Farbe für bessere Deckkraft",
                "Tipp: Möbel sollten abgedeckt oder ausgeräumt werden"
            ]
        }

    def _get_mock_followup_response(self, user_message: str) -> Dict:
        """Mock follow-up response"""
        return {
            "response": "Vielen Dank für die Information. Können Sie mir noch sagen, ob spezielle Vorbereitungen nötig sind?",
            "needs_more_info": True,
            "suggested_questions": [
                "Kleinere Ausbesserungen können den Preis beeinflussen."
            ]
        }

