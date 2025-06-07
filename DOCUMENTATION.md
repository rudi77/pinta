# KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe

**Vollständige Projektdokumentation**

**Version:** 1.0  
**Erstellt am:** 4. Juni 2025  
**Autor:** Manus AI  
**Projekt:** Maler Kostenvoranschlag

---

## Inhaltsverzeichnis

1. [Projektübersicht](#projektübersicht)
2. [Technische Architektur](#technische-architektur)
3. [Installation und Setup](#installation-und-setup)
4. [API-Dokumentation](#api-dokumentation)
5. [Frontend-Dokumentation](#frontend-dokumentation)
6. [Deployment-Anleitung](#deployment-anleitung)
7. [Benutzerhandbuch](#benutzerhandbuch)
8. [Wartung und Support](#wartung-und-support)

---

## Projektübersicht

### Zielsetzung

Das KI-gestützte Kostenvoranschlags-System für Malerbetriebe wurde entwickelt, um kleinen und mittleren Malerbetrieben eine moderne, effiziente Lösung für die Erstellung professioneller Kostenvoranschläge zu bieten. Das System kombiniert künstliche Intelligenz mit benutzerfreundlicher Technologie, um den traditionell zeitaufwändigen Prozess der Angebotserstellung zu revolutionieren.

Die Hauptziele des Systems umfassen die Automatisierung der Planauswertung durch OCR-Technologie und KI-basierte Dokumentenanalyse, die intelligente Generierung von Kostenvoranschlägen basierend auf natürlichsprachlichen Eingaben, die professionelle PDF-Erstellung mit automatischem E-Mail-Versand sowie die Integration eines nachhaltigen Freemium-Geschäftsmodells mit Stripe-Payment-System.

### Zielgruppe

Das System richtet sich primär an Einzelunternehmer und kleine Malerbetriebe mit 1-10 Mitarbeitern, die oft über begrenzte IT-Ressourcen verfügen, aber dennoch professionelle Angebote erstellen müssen. Diese Betriebe benötigen eine Lösung, die ohne umfangreiche Schulungen oder technische Expertise verwendet werden kann, gleichzeitig aber die Qualität und Geschwindigkeit ihrer Angebotserstellung erheblich verbessert.

### Kernfunktionen

Das entwickelte System bietet eine umfassende Suite von Funktionen, die den gesamten Workflow der Angebotserstellung abdecken. Die KI-gestützte Planauswertung ermöglicht es Benutzern, Baupläne, Fotos und bestehende Leistungsverzeichnisse hochzuladen, die automatisch analysiert und in strukturierte Angebotsdaten umgewandelt werden. Die natürlichsprachliche Eingabe erlaubt es Malern, ihre Projekte in gewöhnlicher Sprache zu beschreiben, woraufhin das System intelligente Rückfragen stellt und detaillierte Kostenvoranschläge generiert.

Die automatische PDF-Generierung erstellt professionell formatierte Dokumente mit Firmenbranding, während das integrierte E-Mail-System diese direkt an Kunden versendet. Das Freemium-Modell bietet drei kostenlose Angebote pro Monat, mit flexiblen Upgrade-Optionen über Stripe-Integration.




## Technische Architektur

### Systemarchitektur

Das KI-gestützte Kostenvoranschlags-System folgt einer modernen, mikroservice-orientierten Architektur, die Skalierbarkeit, Wartbarkeit und Performance optimiert. Die Architektur besteht aus drei Hauptkomponenten: einem React-basierten Frontend, einem Flask-Backend mit RESTful API-Design und einer SQLite-Datenbank für lokale Entwicklung mit Migrationspfad zu PostgreSQL für Produktionsumgebungen.

Das Frontend wurde mit React 18 und TypeScript entwickelt, um eine typsichere und performante Benutzeroberfläche zu gewährleisten. Die Verwendung von TailwindCSS und shadcn/ui-Komponenten ermöglicht ein konsistentes, responsives Design, das sowohl auf Desktop- als auch auf mobilen Geräten optimal funktioniert. Das State Management erfolgt über React Hooks und Context API, wodurch eine saubere Trennung von Geschäftslogik und Präsentationsschicht erreicht wird.

Das Backend basiert auf Flask, einem leichtgewichtigen Python-Framework, das sich ideal für RESTful API-Entwicklung eignet. Die Wahl von Flask ermöglicht eine schnelle Entwicklung und einfache Erweiterbarkeit, während gleichzeitig die Flexibilität für komplexe KI-Integrationen gewährleistet wird. SQLAlchemy dient als ORM (Object-Relational Mapping) und abstrahiert die Datenbankoperationen, wodurch eine saubere Trennung zwischen Datenmodell und Geschäftslogik erreicht wird.

### Datenmodell

Das Datenmodell wurde sorgfältig entworfen, um alle Aspekte des Kostenvoranschlags-Workflows abzubilden. Das zentrale `User`-Modell verwaltet Benutzerinformationen, Abonnement-Status und Quota-Limits. Jeder Benutzer kann mehrere `Quote`-Objekte erstellen, die wiederum aus mehreren `QuoteItem`-Objekten bestehen. Diese hierarchische Struktur ermöglicht eine flexible Modellierung komplexer Angebote mit verschiedenen Positionen und Räumen.

Das `Document`-Modell speichert hochgeladene Dateien und deren Metadaten, während das `Payment`-Modell alle Transaktionen und Abonnement-Informationen verwaltet. Die Beziehungen zwischen den Modellen sind durch Foreign Keys und Cascade-Optionen definiert, um Datenintegrität zu gewährleisten.

### KI-Integration

Die KI-Komponenten des Systems nutzen OpenAI's GPT-4o für natürlichsprachliche Verarbeitung und Tesseract OCR für Dokumentenanalyse. Die `AIService`-Klasse kapselt alle KI-Funktionalitäten und bietet eine einheitliche Schnittstelle für verschiedene AI-Operationen. Die Dokumentenanalyse erfolgt durch eine Kombination aus OCR-Texterkennung und KI-basierter Strukturierung, wodurch auch handschriftliche Notizen und komplexe Pläne verarbeitet werden können.

Der KI-Agent für Rückfragen implementiert einen konversationellen Ansatz, bei dem das System gezielt nach fehlenden Informationen fragt und Benutzerantworten in strukturierte Angebotsdaten umwandelt. Dieser Prozess wird durch ein State-Machine-Pattern gesteuert, das verschiedene Phasen der Angebotserstellung verwaltet.

### Sicherheitsarchitektur

Die Sicherheit des Systems basiert auf mehreren Ebenen. Auf der Netzwerkebene werden alle API-Endpunkte durch CORS-Richtlinien geschützt, die nur autorisierte Domains zulassen. Die Authentifizierung erfolgt über JWT-Token mit konfigurierbaren Ablaufzeiten. Alle sensiblen Daten werden verschlüsselt gespeichert, und API-Schlüssel werden über Umgebungsvariablen verwaltet.

Die Datei-Uploads werden durch Größen- und Typ-Validierung geschützt, während hochgeladene Dokumente in isolierten Verzeichnissen gespeichert werden. Die Integration mit Stripe erfolgt über sichere Webhooks mit Signatur-Verifizierung, um die Integrität von Payment-Daten zu gewährleisten.

### Performance-Optimierung

Das System implementiert verschiedene Performance-Optimierungen auf allen Ebenen. Im Frontend werden React.memo und useMemo für Component-Optimierung eingesetzt, während Code-Splitting die initiale Ladezeit reduziert. Das Backend nutzt SQLAlchemy's Lazy Loading und Query-Optimierung, um Datenbankzugriffe zu minimieren.

Für die KI-Verarbeitung werden Requests asynchron abgearbeitet, um die Benutzerfreundlichkeit zu erhalten. Die PDF-Generierung erfolgt über einen Fallback-Mechanismus, der bei Ausfall der CraftMyPDF-API auf lokale ReportLab-Generierung umschaltet.


## Installation und Setup

### Systemvoraussetzungen

Für die erfolgreiche Installation und den Betrieb des KI-gestützten Kostenvoranschlags-Systems sind bestimmte Systemvoraussetzungen erforderlich. Das System wurde für Linux-basierte Umgebungen (Ubuntu 20.04+) entwickelt und getestet, funktioniert aber auch unter macOS und Windows mit entsprechenden Anpassungen.

Die minimalen Hardwareanforderungen umfassen 4 GB RAM, 10 GB freien Festplattenspeicher und eine stabile Internetverbindung für KI-API-Zugriffe. Für Produktionsumgebungen werden 8 GB RAM und SSD-Speicher empfohlen, um optimale Performance zu gewährleisten.

Auf der Softwareseite werden Python 3.11+, Node.js 18+, npm oder yarn, Git für Versionskontrolle und optional Docker für containerisierte Deployments benötigt. Zusätzlich sind Tesseract OCR und poppler-utils für die Dokumentenverarbeitung erforderlich.

### Backend-Installation

Die Backend-Installation beginnt mit dem Klonen des Repositories und der Einrichtung einer Python-Virtual-Environment. Nach dem Navigieren in das Backend-Verzeichnis wird eine virtuelle Umgebung erstellt und aktiviert, gefolgt von der Installation aller erforderlichen Python-Pakete über pip.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# oder: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

Die Konfiguration erfolgt über eine `.env`-Datei, die aus der bereitgestellten `.env.example` erstellt wird. Diese Datei enthält alle erforderlichen Umgebungsvariablen, einschließlich API-Schlüssel für OpenAI, CraftMyPDF und Stripe, sowie E-Mail-Konfiguration und Firmeninformationen.

Für die Datenbankinitialisierung wird SQLite für lokale Entwicklung verwendet, mit automatischer Tabellenerstellung beim ersten Start. Für Produktionsumgebungen kann die Datenbank-URL in der `.env`-Datei auf PostgreSQL oder MySQL geändert werden.

### Frontend-Installation

Die Frontend-Installation erfordert Node.js und npm. Nach dem Navigieren in das Frontend-Verzeichnis werden alle Abhängigkeiten installiert und das Entwicklungsserver gestartet.

```bash
cd frontend
npm install
npm run dev
```

Das Frontend ist so konfiguriert, dass es automatisch mit dem Backend auf Port 5000 kommuniziert. Die Konfiguration kann in der `vite.config.js` angepasst werden, falls andere Ports oder Hosts verwendet werden sollen.

### Systemdienste-Installation

Für die vollständige Funktionalität müssen zusätzliche Systemdienste installiert werden. Tesseract OCR wird für die Dokumentenanalyse benötigt und kann über den Paketmanager installiert werden:

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-deu poppler-utils
```

Die deutsche Sprachunterstützung für Tesseract ist besonders wichtig, da das System primär für den deutschen Markt entwickelt wurde.

### Umgebungsvariablen-Konfiguration

Die Konfiguration des Systems erfolgt ausschließlich über Umgebungsvariablen, um Sicherheit und Flexibilität zu gewährleisten. Die wichtigsten Konfigurationsparameter umfassen:

**OpenAI-Konfiguration:** Der `OPENAI_API_KEY` ist erforderlich für alle KI-Funktionalitäten. Dieser kann über die OpenAI-Plattform bezogen werden und sollte ausreichende Credits für die erwartete Nutzung haben.

**E-Mail-Konfiguration:** Die SMTP-Einstellungen ermöglichen den automatischen Versand von Kostenvoranschlägen. Für Gmail werden App-spezifische Passwörter empfohlen, während für andere Provider entsprechende SMTP-Credentials erforderlich sind.

**Stripe-Konfiguration:** Für das Payment-System werden sowohl Test- als auch Live-Schlüssel von Stripe benötigt. Die Webhook-Konfiguration muss in der Stripe-Konsole eingerichtet werden, um Payment-Events zu verarbeiten.

**Firmeninformationen:** Diese Daten werden in generierten PDFs verwendet und sollten vollständig und korrekt konfiguriert werden, um professionelle Angebote zu erstellen.

### Entwicklungsumgebung

Für die Entwicklung wird eine lokale Umgebung mit Hot-Reload-Funktionalität empfohlen. Das Backend kann mit `python src/main.py` gestartet werden, während das Frontend über `npm run dev` läuft. Beide Services unterstützen automatisches Neuladen bei Codeänderungen.

Die Entwicklungsumgebung nutzt SQLite als Datenbank, was keine zusätzliche Konfiguration erfordert. Für erweiterte Entwicklung kann eine lokale PostgreSQL-Instanz eingerichtet werden, um Produktionsbedingungen zu simulieren.

### Produktionssetup

Für Produktionsumgebungen sind zusätzliche Konfigurationen erforderlich. Das Backend sollte über einen WSGI-Server wie Gunicorn betrieben werden, während das Frontend als statische Dateien über einen Webserver wie Nginx bereitgestellt wird.

Die Datenbank sollte auf eine robuste Lösung wie PostgreSQL migriert werden, mit regelmäßigen Backups und Monitoring. SSL-Zertifikate sind für alle öffentlichen Endpunkte erforderlich, und Firewall-Regeln sollten nur notwendige Ports freigeben.

Logging und Monitoring sind kritische Komponenten für Produktionsumgebungen. Das System unterstützt strukturiertes Logging über Python's logging-Modul, und Metriken können über Tools wie Prometheus und Grafana überwacht werden.

