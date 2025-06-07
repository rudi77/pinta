Sehr gerne! Hier eine **Taskliste** in der optimalen Reihenfolge, mit jeweils kurzen Erklärungen. Du kannst diese direkt für Sprint-Planning, Jira oder GitHub Issues verwenden.

---

## **Taskliste: Chat-basierte Kostenvoranschlagserstellung**

### **1. Backend-Tasks**

1. **\[ ] Analyse und Erweiterung der API-Endpunkte**

   * Prüfe, ob `/ai/analyze-input`, `/ai/ask-question` und `/ai/generate-quote` alle nötigen Infos und passenden Responses für den Chatflow liefern.
2. **\[ ] Conversation-History im Quote-Modell ergänzen**

   * Neues Feld (z.B. `ai_conversation_history: JSON/Text`) im Quote-Model und Datenbankschema ergänzen.
3. **\[ ] Optional: KI-Erstellungs-Flag im Quote-Modell**

   * Feld wie `created_by_ai: Boolean` für spätere Auswertung hinzufügen.
4. **\[ ] Anpassung der Speichern-/Erstellen-Logik**

   * Sicherstellen, dass der finale Quote aus der KI direkt gespeichert und als PDF generiert werden kann.
5. **\[ ] Datei-Upload-Endpoint für Pläne/Fotos absichern**

   * Prüfe `/upload-document` und optimiere Fehlerbehandlung, falls notwendig.

---

### **2. Frontend-Tasks**

6. **\[ ] Neue Chat-Komponente anlegen (`ChatQuoteWizard`)**

   * Initiales Setup als eigenständiges Modul/Component im UI.
7. **\[ ] KI-API-Services implementieren**

   * Frontend-Services für alle `/ai/`- und `/quotes/`-Endpoints bauen.
8. **\[ ] Chat UI: Nachrichten- und Verlaufskomponenten**

   * Chat-Verlauf visuell abbilden, mit Unterscheidung KI/Nutzer.
9. **\[ ] Eingabefelder dynamisch generieren**

   * Je nach KI-Fragetyp: Text, Multiple-Choice, Datei-Upload.
10. **\[ ] Dateiupload im Chat integrieren**

    * Upload-Funktion im Chat (Pläne/Fotos), Anzeige des Analyse-Feedbacks.
11. **\[ ] State-Handling für Konversations- und Angebotsdaten**

    * Verlauf, aktuelle Fragen/Antworten, und finalen Quote im State halten.
12. **\[ ] Abschluss-Flow: Angebot speichern & PDF erzeugen**

    * Nach Abschluss: Button für "Speichern & PDF", Rückmeldung im Chat.
13. **\[ ] Bestehenden Step-by-Step-Wizard deaktivieren/entfernen**

    * Optional: als Fallback erhalten oder komplett entfernen.
14. **\[ ] Testing und Error Handling**

    * UX-Tests für Edge Cases, Fehler beim KI-Call, etc.

---

### **3. UX & Review**

15. **\[ ] UI/UX Review mit Testnutzer(n)**

    * Feedback zum neuen Flow einholen und Verbesserungen einarbeiten.
16. **\[ ] Dokumentation & Changelog aktualisieren**

    * README, API-Docs und Benutzerhandbuch mit neuen Features erweitern.

---

### **4. Go-Live**

17. **\[ ] Deployment vorbereiten (Backend & Frontend)**

    * Staging/Produktivsysteme aufsetzen oder aktualisieren.
18. **\[ ] Monitoring der neuen Funktionalität**

    * Logging und Fehlertracking für den neuen Chatflow aktivieren.
19. **\[ ] Altes UI ggf. endgültig entfernen**
