# KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe

Ein innovatives System zur automatischen Erstellung professioneller Kostenvoranschläge mit KI-Unterstützung, OCR-Dokumentenanalyse und integriertem Payment-System.

## 🚀 Features

- **KI-gestützte Planauswertung** - Automatische Analyse von Bauplänen und Dokumenten
- **Natürlichsprachliche Eingabe** - Beschreiben Sie Projekte in gewöhnlicher Sprache
- **Intelligente Rückfragen** - KI-Agent stellt gezielte Fragen für vollständige Angebote
- **Professionelle PDF-Generierung** - Automatische Erstellung formatierter Kostenvoranschläge
- **E-Mail-Integration** - Direkter Versand an Kunden
- **Freemium-Modell** - 3 kostenlose Angebote pro Monat, Premium-Upgrade verfügbar
- **Responsive Design** - Optimiert für Desktop und Mobile

## 🛠 Technologie-Stack

### Frontend
- **React 18** mit TypeScript
- **TailwindCSS** für Styling
- **shadcn/ui** Komponenten
- **Vite** als Build-Tool

### Backend
- **Flask** (Python) REST API
- **SQLAlchemy** ORM
- **OpenAI GPT-4o** für KI-Funktionen
- **Tesseract OCR** für Dokumentenanalyse
- **Stripe** für Payments

### Services
- **CraftMyPDF** für PDF-Generierung
- **SMTP** für E-Mail-Versand
- **SQLite/PostgreSQL** Datenbank

## 📋 Voraussetzungen

- Python 3.11+
- Node.js 18+
- Git
- Tesseract OCR

## 🔧 Installation

### 1. Repository klonen
```bash
git clone <repository-url>
cd maler-kostenvoranschlag
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

### 3. Umgebungsvariablen konfigurieren
```bash
cp .env.example .env
# .env-Datei mit Ihren API-Schlüsseln bearbeiten
```

### 4. Frontend Setup
```bash
cd ../frontend
npm install
```

### 5. Systemdienste installieren
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-deu poppler-utils
```

## 🚀 Entwicklung starten

### Backend starten
```bash
cd backend
source venv/bin/activate
python src/main.py
```
Backend läuft auf: http://localhost:5000

### Frontend starten
```bash
cd frontend
npm run dev
```
Frontend läuft auf: http://localhost:5173

## 📁 Projektstruktur

```
maler-kostenvoranschlag/
├── backend/
│   ├── src/
│   │   ├── models/          # Datenbankmodelle
│   │   ├── routes/          # API-Endpunkte
│   │   ├── services/        # Business Logic
│   │   └── main.py          # Flask-App
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      # React-Komponenten
│   │   ├── hooks/           # Custom Hooks
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── DOCUMENTATION.md         # Technische Dokumentation
├── API_DOCUMENTATION.md     # API-Referenz
├── BENUTZERHANDBUCH.md     # Benutzeranleitung
└── README.md
```

## 🔑 Umgebungsvariablen

Erstellen Sie eine `.env`-Datei im Backend-Verzeichnis:

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# CraftMyPDF
CRAFTMYPDF_API_KEY=your_craftmypdf_api_key
CRAFTMYPDF_TEMPLATE_ID=your_template_id

# E-Mail
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_test_your_key
STRIPE_SECRET_KEY=sk_test_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_secret

# Firma
COMPANY_NAME=Ihr Malerbetrieb
COMPANY_EMAIL=info@malerbetrieb.de
COMPANY_PHONE=+49 123 456789
```

## 📖 Dokumentation

- **[Technische Dokumentation](DOCUMENTATION.md)** - Architektur und Implementierung
- **[API-Dokumentation](API_DOCUMENTATION.md)** - REST API Referenz
- **[Benutzerhandbuch](BENUTZERHANDBUCH.md)** - Anleitung für Endbenutzer

## 🧪 Testing

### Backend Tests
```bash
cd backend
source venv/bin/activate
python -m pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 🚀 Deployment

### Produktions-Build
```bash
# Frontend Build
cd frontend
npm run build

# Backend für Produktion konfigurieren
cd ../backend
# Umgebungsvariablen für Produktion setzen
# WSGI-Server wie Gunicorn verwenden
```

### Docker (Optional)
```bash
# Docker-Images erstellen
docker-compose build

# Services starten
docker-compose up -d
```

## 🔒 Sicherheit

- Alle API-Endpunkte sind durch CORS geschützt
- JWT-Token für Authentifizierung
- Verschlüsselte Datenübertragung (HTTPS)
- DSGVO-konforme Datenspeicherung
- Sichere Stripe-Integration mit Webhook-Verifizierung

## 📊 Features im Detail

### KI-Funktionen
- **Dokumentenanalyse**: OCR-basierte Texterkennung aus Plänen und Fotos
- **Intelligente Extraktion**: Automatische Erkennung von Räumen, Maßen und Arbeitstypen
- **Rückfrage-System**: Gezielte Nachfragen bei unvollständigen Informationen
- **Preisberechnung**: KI-gestützte Kalkulation basierend auf Marktdaten

### Business-Features
- **Freemium-Modell**: 3 kostenlose Angebote/Monat
- **Premium-Abonnement**: Unbegrenzte Angebote für 29,99€/Monat
- **Zusatzkäufe**: 10 Angebote für 19,99€
- **Automatische Abrechnung**: Stripe-Integration mit Webhooks

### Benutzerfreundlichkeit
- **Responsive Design**: Optimiert für alle Geräte
- **Intuitive Navigation**: Klare Benutzerführung
- **Demo-Modus**: Sofortiger Test ohne Registrierung
- **Mehrsprachig**: Deutsch als Hauptsprache

## 🤝 Beitragen

1. Fork des Repositories
2. Feature-Branch erstellen (`git checkout -b feature/AmazingFeature`)
3. Änderungen committen (`git commit -m 'Add some AmazingFeature'`)
4. Branch pushen (`git push origin feature/AmazingFeature`)
5. Pull Request erstellen

## 📝 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

## 📞 Support

- **E-Mail**: support@maler-kostenvoranschlag.de
- **Dokumentation**: Siehe Dokumentations-Dateien
- **Issues**: GitHub Issues für Bug-Reports und Feature-Requests

## 🎯 Roadmap

- [ ] Mobile App (React Native)
- [ ] Erweiterte KI-Modelle
- [ ] Integration mit Buchhaltungssoftware
- [ ] Multi-Tenant-Architektur
- [ ] API für Drittanbieter
- [ ] Erweiterte Reporting-Features

## 👥 Team

Entwickelt von **Manus AI** - Spezialisiert auf KI-gestützte Business-Lösungen.

---

**Version**: 1.0  
**Letztes Update**: 4. Juni 2025

