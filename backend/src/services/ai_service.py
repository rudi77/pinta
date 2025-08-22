import openai
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import base64
from core.settings import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        api_key = settings.openai_api_key
        if api_key and api_key != 'test_key_placeholder' and api_key.startswith('sk-'):
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = "gpt-4o-mini"  # Updated to use latest fast model
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

