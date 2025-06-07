Sehr gerne! Hier eine **aktualisierte Taskliste** in der optimalen Reihenfolge, mit jeweils kurzen Erklärungen. Bereits erledigte Aufgaben sind abgehakt.

---

## **Taskliste: Chat-basierte Kostenvoranschlagserstellung & Angebots-Detailansicht**

### **1. Backend-Tasks**

1. **[x] Analyse und Erweiterung der API-Endpunkte**
   * `/ai/analyze-input`, `/ai/ask-question` und `/ai/generate-quote` geprüft und für Chatflow genutzt.
2. **[x] Conversation-History im Quote-Modell ergänzen**
   * Feld `ai_conversation_history: JSON/Text` im Quote-Model und Datenbankschema ergänzt.
3. **[x] Optional: KI-Erstellungs-Flag im Quote-Modell**
   * Feld wie `created_by_ai: Boolean` für spätere Auswertung hinzugefügt.
4. **[x] Anpassung der Speichern-/Erstellen-Logik**
   * Sicherstellen, dass der finale Quote aus der KI direkt gespeichert und als PDF generiert werden kann.
5. **[x] Fehlerbehandlung & Response-Format für Quote-Detail**
   * Endpunkt `/quotes/{quote_id}` liefert jetzt korrekt gemapptes Response-Objekt (inkl. Items, Conversation-History als Liste, leere Strings statt None).
6. **[ ] Datei-Upload-Endpoint für Pläne/Fotos absichern**
   * Prüfe `/upload-document` und optimiere Fehlerbehandlung, falls notwendig.

---

### **2. Frontend-Tasks**

6. **[x] Neue Chat-Komponente anlegen (`ChatQuoteWizard`)**
   * Initiales Setup als eigenständiges Modul/Component im UI.
7. **[x] KI-API-Services implementieren**
   * Frontend-Services für alle `/ai/`- und `/quotes/`-Endpoints gebaut.
8. **[x] Chat UI: Nachrichten- und Verlaufskomponenten**
   * Chat-Verlauf visuell abgebildet, mit Unterscheidung KI/Nutzer.
9. **[x] Eingabefelder dynamisch generieren**
   * Je nach KI-Fragetyp: Text, Multiple-Choice, Datei-Upload.
10. **[x] Dateiupload im Chat integrieren**
    * Upload-Funktion im Chat (Pläne/Fotos), Anzeige des Analyse-Feedbacks.
11. **[x] State-Handling für Konversations- und Angebotsdaten**
    * Verlauf, aktuelle Fragen/Antworten, und finalen Quote im State halten.
12. **[x] Abschluss-Flow: Angebot speichern & PDF erzeugen**
    * Nach Abschluss: Button für "Speichern & PDF", Rückmeldung im Chat.
13. **[x] Bestehenden Step-by-Step-Wizard deaktivieren/entfernen**
    * Optional: als Fallback erhalten oder komplett entfernen.
14. **[x] Angebots-Übersicht (Quote-Liste) im Dashboard**
    * Quotes werden im Dashboard als Tabelle angezeigt, inkl. Status, Kunde, Betrag etc.
15. **[x] Angebots-Detailansicht**
    * Klick auf Quote öffnet Detailseite mit allen Infos, Positionen und KI-Dialog.
16. **[x] Fehlerbehandlung für Lade-/API-Fehler**
    * Fehler werden im UI angezeigt.

---

### **3. UX & Review**

17. **[ ] UI/UX Review mit Testnutzer(n)**
    * Feedback zum neuen Flow einholen und Verbesserungen einarbeiten.
18. **[ ] Dokumentation & Changelog aktualisieren**
    * README, API-Docs und Benutzerhandbuch mit neuen Features erweitern.

---

### **4. Go-Live**

19. **[ ] Deployment vorbereiten (Backend & Frontend)**
    * Staging/Produktivsysteme aufsetzen oder aktualisieren.
20. **[ ] Monitoring der neuen Funktionalität**
    * Logging und Fehlertracking für den neuen Chatflow aktivieren.
21. **[ ] Altes UI ggf. endgültig entfernen**

---

**Status:**
- Alle Kernfunktionen für die Angebotsanzeige und Detailansicht sind jetzt umgesetzt.
- Es fehlen nur noch Review, Doku und Go-Live-Schritte.
