Hier kommt eine **Analyse deines aktuellen Systems** und ein **konkreter Feature-Request** inkl. Refactoring-Plan, damit die Kostenvoranschlagserstellung vollständig per Chat mit einem KI-Agenten im Frontend möglich ist.

---

## 1. **Ausgangslage & Analyse**

### **Backend**

* Die bestehende Architektur ist modern (FastAPI, async, saubere Models für User, Quote, QuoteItem, Document, Payment).
* Es gibt bereits eine **AIService-Klasse** mit Methoden für:

  * Analyse der Projektbeschreibung (KI generiert Rückfragen)
  * Bearbeiten von Nutzerantworten und Erstellen eines Angebots (Quote) mit KI
  * Folgefragen im Chat-Kontext (Konversationshistorie)
* KI-Endpunkte sind unter `/ai` in der API sauber getrennt:

  * `/analyze-input`: Projektanalyse & Rückfragen generieren
  * `/ask-question`: Folgefragen stellen und beantworten
  * `/generate-quote`: Aus allen gesammelten Antworten finalen Kostenvoranschlag bauen
* Die PDF-Generierung & E-Mail-Versand ist als Service gekapselt und kann ein Quote-Objekt als PDF rendern.

### **Frontend**

* Die Frontend-Codebasis ist modular, basiert auf React mit Komponenten (TypeScript, shadcn/ui, Tailwind).
* Aktuell ist die Angebots-/Quote-Erstellung aber **in 4 festen Schritten** umgesetzt.
* Es gibt **keine zentrale Chat-Komponente**, die eine interaktive, dynamische Konversation mit der KI (inkl. Rückfragen & Antworten) abbildet.
* Es fehlt eine Funktionalität, um am Ende der Konversation den erzeugten Kostenvoranschlag direkt zu speichern und als PDF zu generieren.

### **Dokumentation**

* Die technische Architektur beschreibt den geplanten Chat-Flow als KI-Workflow (State Machine mit Rückfragen/Antworten, Abschluss als Quote).
* Die API bietet schon (fast) alles, um einen Chatbot-gesteuerten Flow zu bauen.

---

## 2. **Feature-Request Dokument: "Chat-basierte Kostenvoranschlagserstellung"**

### **Ziel**

Der Nutzer kann im Chat mit der KI sein Projekt beliebig beschreiben, beliebig Rückfragen beantworten und am Ende einen vollständigen Kostenvoranschlag als PDF speichern. Kein fester Wizard-Flow mehr.

---

### **Neue/Geänderte Features**

#### **Frontend**

1. **Neue Chat-Komponente**

   * Volle Integration aller Backend-AI-APIs als "Conversational UI":

     * Nutzer gibt beliebige Projektbeschreibung ein (Freitext).
     * KI analysiert den Text, stellt Rückfragen (Multiple-Choice/Text/Nummer).
     * Nutzer beantwortet Rückfragen (als Chat-Formular).
     * KI fragt ggf. nach ("Haben Sie noch Wünsche?"), bis alle Infos für ein Angebot gesammelt wurden.
     * Sobald genug Infos vorliegen: Button "Kostenvoranschlag erstellen" wird aktiv.
   * **Konversationsspeicher:** Verlauf der bisherigen Fragen & Antworten lokal (oder per `/conversation-history/{quote_id}`) speichern & anzeigen.
   * **Datei-Upload im Chat:** Optional, falls der User Grundrisse/Fotos hochladen will (nutzt `/upload-document`).
   * **State-Handling:** Der Chat-Flow ist so lange offen, bis das Angebot generiert wurde.

2. **Quote-Generierung und PDF-Download**

   * Im letzten Chat-Step: User kann den erarbeiteten Kostenvoranschlag direkt "speichern" (POST `/quotes/` oder `/ai/generate-quote`).
   * Nach Speicherung: "PDF erstellen" (Backend-Service nutzen) & Download-Link/Anzeige.
   * Option: Angebots-PDF per Mail an Kunden versenden.

3. **UX/Design**

   * Chat-Verlauf optisch sauber abtrennen (Fragen/Antworten, KI/Nutzer).
   * Lade- und Fehlerzustände bei KI-Calls.
   * Übersicht: Nachträglich alle bisherigen Kostenvoranschläge einsehbar (bisheriges Quotes-Listing bleibt).

#### **Backend**

1. **API-Endpunkte prüfen & anpassen**

   * Die bestehenden Endpunkte `/ai/analyze-input`, `/ai/ask-question`, `/ai/generate-quote` sind geeignet.
   * Sicherstellen, dass der finale Quote wie gewohnt ins DB-Modell geschrieben werden kann (evtl. Anpassung an den Output von `/ai/generate-quote`).
   * Conversation-History ggf. persistent im Quote-Objekt speichern (z. B. als JSON-Feld "ai\_conversation" im Quote-Modell, wenn Du echten Verlauf speichern willst).

2. **Datei-Upload & Plananalyse**

   * Optional: KI-Analyse von Plänen/Fotos per `/ai/upload-document` weiter ausbauen (noch "in Entwicklung", laut Code).

3. **KI-Flow-Logik (optional)**

   * Ein optionales Flag im Quote: Wurde dieses Angebot per Chat/KI erstellt? (Zur Auswertung/Statistik)
   * Den gesamten Q\&A-Dialog optional als JSON im Quote speichern (für Audit/UX-Auswertung).

#### **Datenmodell**

* Quote ggf. erweitern um:

  * `ai_conversation_history: Text/JSON` (optional)
  * `created_by_ai: Boolean` (optional)

---

### **Konkrete Refactoring-Maßnahmen**

#### **Frontend**

1. **Neues Modul: `ChatQuoteWizard`**

   * Basiert auf React-Context für Konversationsstatus.
   * Nutzt alle relevanten Backend-APIs, um User-Input → KI → Rückfragen → User-Answer → ... → Angebot zu orchestrieren.
   * UI: Chat-Bubbles, dynamische Eingabefelder (Multiple-Choice/Text).
   * Finaler Step: Angebots-Objekt aus Antworten bauen, per API speichern und PDF erzeugen.
2. **Entfernung/Abschalten des bisherigen Multi-Step-Quote-Wizard**

   * Optional: Legacy-Flow als Fallback erhalten, aber neue Nutzerführung auf Chat-Flow setzen.
3. **Integration von Dokumenten-Upload direkt im Chat**

   * Für Pläne/Fotos optional einen Upload-Button im Chat anbieten, nach Upload Ergebnis anzeigen und evtl. in das Angebot einfließen lassen.

#### **Backend**

1. **Sicherstellen, dass KI-basierte Angebotsdaten nahtlos ins bestehende Quote/QuoteItem-Modell übernommen werden können.**
2. **API ggf. um Conversation-History-Feld für Quotes erweitern.**

   * Neue Feld in Datenbankmigration + Models + Schema
3. **(Optional) Conversation-Verlauf & KI-Status in Quote mitschreiben.**

   * Evtl. eigenes AIQuote-Flag (für Reporting).

---

### **API-Flow (aus Frontend-Sicht)**

1. **Nutzer-Text → `/ai/analyze-input`**

   * Rückfragen & Analyse
2. **User-Antwort → `/ai/ask-question`**

   * Rückfragen, falls noch nicht alles geklärt
3. **Alle Infos gesammelt → `/ai/generate-quote`**

   * Finale Angebotsdaten und Items generieren lassen
4. **Quote speichern → `/quotes/`**

   * Angebot persistieren, optional Conversation-History mitschicken
5. **PDF erzeugen → `/pdf/generate` (oder analog via PDF-Service)**

   * Download-Link, Anzeige, oder Mail an Kunden

---

## 3. **Zusammenfassung: Was ist zu tun?**

### **Frontend**

* [ ] Chat-Komponente für Q\&A-Flow mit KI bauen (React)
* [ ] Alle KI-APIs als Service integrieren
* [ ] State-Handling & Verlauf
* [ ] Datei-Upload direkt im Chat
* [ ] PDF- und Angebotsspeicher-Funktionen direkt aus Chat triggern
* [ ] Bestehenden Multi-Step-Quote-Wizard abschalten/ersetzen

### **Backend**

* [ ] Endpunkte auf "Chat-Flow" testen und ggf. Response/Schema angleichen
* [ ] (Optional) Conversation-History und KI-Flag im Quote-Model ergänzen
* [ ] Dokumenten-Upload (KI-Analyse) stabilisieren/ausbauen
* [ ] Endpunkte für PDF-Generierung & E-Mail-Versand für neue Nutzung absichern

---

## 4. **Mini-Mockup des neuen Chat-Flows (Frontend)**

```
[User]: "Ich möchte meine 2 Zimmer Wohnung (50m²) komplett streichen lassen, Decke weiß, Wände hellblau, vorherige Farbe entfernen."
[KI]:   "Wie hoch sind die Decken in den Räumen?"
[User]: "2,50 m"
[KI]:   "Sollen wir das Material bereitstellen?"
[User]: "Ja, bitte."
[KI]:   "Sind Möbel zu schützen oder zu verrücken?"
[User]: "Einige Möbel sind vorhanden, sollten abgedeckt werden."
[KI]:   "Möchten Sie einen Kostenvoranschlag erstellen lassen?"
[User]: "Ja."
[KI]:   "[Zusammenfassung: ...] → Angebot ist bereit."
[Button: Kostenvoranschlag speichern/PDF erstellen]
```

---

## **Fazit**

Mit minimalen Backend-Anpassungen und einer neuen zentralen Chat-Komponente im Frontend lässt sich das gesamte Angebotswesen auf einen Chatbot-basierten Prozess umstellen. Das System ist bereits dafür vorbereitet, der Refactoring-Aufwand hält sich in Grenzen – Fokus liegt auf neuer UI/UX und smarter API-Orchestrierung.

---

**Wenn du möchtest, kann ich dir sofort ein Feature-Ticket oder eine User Story im gewünschten Format schreiben. Sag einfach Bescheid!**
