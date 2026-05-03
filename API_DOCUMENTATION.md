# API-Dokumentation

**Pinta — KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe**

**Version:** 2.x (unified agent)
**Base URL (dev):** `http://localhost:8000`
**Backend:** FastAPI (Python 3.11+) — der ursprüngliche Manus-AI-Scaffold
hatte Flask im README, der aktuelle Code ist FastAPI.

---

## Übersicht

Pinta unterstützt zwei Arten von Konsumenten:

1. **Web App + REST-Klienten** — JWT-basierte Authentifizierung über
   `Authorization: Bearer <jwt_token>`. Verwenden hauptsächlich die
   neuen `/api/v1/agent/*` Endpunkte.
2. **Telegram-Bot (oder andere Channel-Adapter)** — eigenes Auth-Schema
   über drei Header (`X-Bot-Service-Token`, `X-Channel`, `X-External-Id`),
   verwenden den `/api/v1/agent/bot/*` Sub-Namespace.

Beide laufen gegen denselben Agent (Manfred, pytaskforce LeanAgent),
schreiben in dieselbe DB (`Quote`, `Document`, `Conversation`,
`ConversationMessage`, `ChannelLink`) und teilen sich Quota,
Material-Datenbank und PDF-Storage.

## Authentifizierung

### JWT (Web + REST-Klienten)

```
Authorization: Bearer <jwt_token>
```

Token wird über `/api/v1/auth/login` bezogen.

### Bot-Service-Token (Channel-Adapter)

```
X-Bot-Service-Token: <langer Random-Secret aus .env BOT_SERVICE_TOKEN>
X-Channel: telegram
X-External-Id: <Telegram chat_id>
X-Display-Name: Optional Klarname für Logs/UI
```

Der `BOT_SERVICE_TOKEN` ist ein einmaliger geteilter Secret zwischen
Backend und Bot. Liegt in derselben `.env`-Datei.

---

## Unified Agent API (empfohlen für alle neuen Integrationen)

Alle Quote-Logik geht über diese Endpoints. Sie kapseln den pytaskforce-
Agent inkl. Tool-Use (python-Calculator, search_materials, save_quote_to_db,
generate_quote_pdf, multimedia).

### POST /api/v1/agent/chat

Eine Mission ausführen, sync.

**Request:**
```json
{
  "message": "Schlafzimmer 14m² Wohnfläche streichen, Standard-Dispersion weiß",
  "attachments": [
    {"file_path": "/path/to/photo.jpg", "file_name": "raum.jpg", "type": "image"}
  ],
  "channel": "web"
}
```

**Response:**
```json
{
  "conversation_id": 42,
  "final_message": "...",
  "humanized_message": "Schlafzimmer streichen\nNetto: 770,00 EUR · MwSt 19%: 146,30 EUR · Brutto: 916,30 EUR\nAnnahme: 53,7 m² Streichfläche.\n📄 PDF kommt gleich als Download.",
  "pdf_url": "/api/v1/agent/pdf/20260503_143012_schlafzimmer.pdf",
  "pdf_filename": "20260503_143012_schlafzimmer.pdf",
  "quote_number": "KV-20260503-143012-abc123",
  "status": "completed"
}
```

### POST /api/v1/agent/chat/stream

Server-Sent Events. Jede Zeile: `data: <json>\n\n`. Event-Typen:
`llm_token` (real-time text), `tool_call`, `tool_result`,
`final_answer`, `channel.summary` (mit `pdf_url` und `humanized_message`).

### GET /api/v1/agent/conversations

Liste der Conversations des authentifizierten Users.

### GET /api/v1/agent/conversations/{conversation_id}/messages

Volltext-Transcript einer Conversation.

### POST /api/v1/agent/reset

Aktive Conversation archivieren, neue starten.

### GET /api/v1/agent/pdf/{name}

PDF-Download (auth-gated, Path-Traversal-geschützt).

### POST /api/v1/agent/linking-token

Web-User erzeugt einen 24h-Token, den er in Telegram via `/link <token>`
einlöst. Bindet einen Telegram-Chat an den Pinta-Account.

**Response:**
```json
{
  "token": "abc123...",
  "expires_at": "2026-05-04T14:30:00",
  "channel": "telegram",
  "instruction": "Schick im Telegram-Chat: /link abc123..."
}
```

### Bot-Adapter Endpoints

`POST /api/v1/agent/bot/chat`, `/bot/reset`, `/bot/link` — gleiche Logik
wie die JWT-Pendants, nur mit Bot-Service-Token-Auth. Schatten-User
werden bei erstem Kontakt automatisch angelegt.

---

## Legacy AI Endpoints (backward-compatible)

### POST /api/v1/ai/quick-quote

**Wichtig:** Dieses Endpoint hat seine **Response-Schema unverändert**
behalten, läuft intern aber jetzt durch den unified Agent. Heißt: jeder
Web-Quote landet ab sofort in `Conversation`/`ConversationMessage`/
`Quote`-Tabellen — sichtbar im Web-Dashboard und (falls verlinkt) im
Telegram-Verlauf.

### POST /api/v1/ai/analyze-project, POST /api/v1/ai/generate-quote

Noch auf dem Legacy-Single-Shot-`AIService`-Pfad. Werden migriert, sobald
das Frontend auf `/api/v1/agent/chat` umsteigt.

### POST /api/v1/ai/upload-document, /api/v1/ai/visual-estimate, ...

Unverändert.

---

## Klassische Auth- und CRUD-Endpoints

## Benutzer-Endpunkte

### POST /api/users/register

Registriert einen neuen Benutzer im System.

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "company_name": "string (optional)",
  "phone": "string (optional)"
}
```

**Response:**
```json
{
  "success": true,
  "user_id": 1,
  "message": "User registered successfully"
}
```

### POST /api/users/login

Authentifiziert einen Benutzer und gibt ein JWT-Token zurück.

**Request Body:**
```json
{
  "email": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "success": true,
  "token": "jwt_token_string",
  "user": {
    "id": 1,
    "username": "string",
    "email": "string",
    "is_premium": false,
    "quotes_this_month": 1
  }
}
```

### GET /api/users/profile

Gibt das Profil des aktuell authentifizierten Benutzers zurück.

**Response:**
```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "string",
    "email": "string",
    "company_name": "string",
    "phone": "string",
    "is_premium": false,
    "premium_until": "2025-12-31T23:59:59",
    "quotes_this_month": 1,
    "additional_quotes": 0
  }
}
```

## Angebots-Endpunkte

### GET /api/quotes

Gibt alle Angebote des aktuellen Benutzers zurück.

**Query Parameters:**
- `status` (optional): Filtert nach Angebotsstatus (draft, completed, sent)
- `limit` (optional): Begrenzt die Anzahl der Ergebnisse
- `offset` (optional): Offset für Paginierung

**Response:**
```json
{
  "success": true,
  "quotes": [
    {
      "id": 1,
      "quote_number": "KV-20250604-143022",
      "customer_name": "Max Mustermann",
      "customer_email": "max@example.com",
      "project_title": "Wohnzimmer streichen",
      "total_amount": 1250.00,
      "status": "draft",
      "created_at": "2025-06-04T14:30:22",
      "updated_at": "2025-06-04T14:30:22"
    }
  ]
}
```

### POST /api/quotes

Erstellt ein neues Angebot.

**Request Body:**
```json
{
  "customer_name": "string",
  "customer_email": "string (optional)",
  "customer_phone": "string (optional)",
  "customer_address": "string (optional)",
  "project_title": "string",
  "project_description": "string (optional)",
  "quote_items": [
    {
      "position": 1,
      "description": "Wandflächen streichen",
      "quantity": 25.5,
      "unit": "m²",
      "unit_price": 15.00,
      "total_price": 382.50,
      "room_name": "Wohnzimmer",
      "area_sqm": 25.5
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "quote_id": 1,
  "quote_number": "KV-20250604-143022"
}
```

### GET /api/quotes/{quote_id}

Gibt ein spezifisches Angebot mit allen Details zurück.

**Response:**
```json
{
  "success": true,
  "quote": {
    "id": 1,
    "quote_number": "KV-20250604-143022",
    "customer_name": "Max Mustermann",
    "customer_email": "max@example.com",
    "customer_phone": "+49 123 456789",
    "customer_address": "Musterstraße 123, 12345 Musterstadt",
    "project_title": "Wohnzimmer streichen",
    "project_description": "Komplette Renovierung des Wohnzimmers",
    "total_amount": 1250.00,
    "labor_hours": 16.0,
    "hourly_rate": 45.00,
    "material_cost": 530.00,
    "additional_costs": 0.00,
    "status": "draft",
    "ai_processing_status": "completed",
    "created_at": "2025-06-04T14:30:22",
    "updated_at": "2025-06-04T14:30:22",
    "quote_items": [
      {
        "id": 1,
        "position": 1,
        "description": "Wandflächen grundieren und streichen",
        "quantity": 25.5,
        "unit": "m²",
        "unit_price": 15.00,
        "total_price": 382.50,
        "room_name": "Wohnzimmer",
        "area_sqm": 25.5
      }
    ]
  }
}
```

### POST /api/quotes/{quote_id}/generate-pdf

Generiert ein PDF für das angegebene Angebot.

**Response:**
```json
{
  "success": true,
  "pdf_url": "https://api.craftmypdf.com/download/...",
  "download_url": "https://api.craftmypdf.com/download/..."
}
```

Oder bei lokaler PDF-Generierung wird die PDF-Datei direkt als Download zurückgegeben.

### POST /api/quotes/{quote_id}/send-email

Sendet das Angebot per E-Mail an den Kunden.

**Response:**
```json
{
  "success": true,
  "message": "Quote sent successfully"
}
```

## KI-Endpunkte

### POST /api/ai/analyze-input

Analysiert Benutzereingaben und generiert Rückfragen oder Angebotsdaten.

**Request Body:**
```json
{
  "input": "Wohnzimmer, 25 m², weiß streichen, ca. 10 Stunden Arbeit",
  "context": "initial_input"
}
```

**Response:**
```json
{
  "success": true,
  "analysis": {
    "confidence": 0.85,
    "extracted_data": {
      "room_name": "Wohnzimmer",
      "area_sqm": 25,
      "work_type": "streichen",
      "color": "weiß",
      "estimated_hours": 10
    },
    "questions": [
      "Welche Wandhöhe hat das Wohnzimmer?",
      "Sollen auch Decke und Türrahmen gestrichen werden?"
    ],
    "suggested_items": [
      {
        "description": "Wandflächen grundieren und streichen",
        "quantity": 25,
        "unit": "m²",
        "unit_price": 15.00,
        "total_price": 375.00
      }
    ]
  }
}
```

### POST /api/ai/upload-document

Lädt ein Dokument hoch und analysiert es mit OCR und KI.

**Request:** Multipart/form-data mit Datei

**Response:**
```json
{
  "success": true,
  "document_id": 1,
  "analysis": {
    "extracted_text": "Grundriss Wohnzimmer 5m x 5m...",
    "detected_rooms": [
      {
        "name": "Wohnzimmer",
        "area_sqm": 25,
        "dimensions": "5m x 5m"
      }
    ],
    "suggested_work": [
      {
        "description": "Wandflächen streichen",
        "area_sqm": 80,
        "estimated_hours": 12
      }
    ]
  }
}
```

## Payment-Endpunkte

### POST /api/payments/create-checkout-session

Erstellt eine Stripe-Checkout-Session für Premium-Upgrade.

**Request Body:**
```json
{
  "success_url": "https://example.com/success",
  "cancel_url": "https://example.com/cancel"
}
```

**Response:**
```json
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/pay/...",
  "session_id": "cs_test_..."
}
```

### POST /api/payments/create-additional-quotes-session

Erstellt eine Checkout-Session für zusätzliche Angebote.

**Request Body:**
```json
{
  "amount": 19.99,
  "description": "10 zusätzliche Angebote",
  "success_url": "https://example.com/success",
  "cancel_url": "https://example.com/cancel"
}
```

**Response:**
```json
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/pay/...",
  "session_id": "cs_test_..."
}
```

### GET /api/payments/quota-info

Gibt Informationen über das aktuelle Kontingent des Benutzers zurück.

**Response:**
```json
{
  "success": true,
  "quota": {
    "is_premium": false,
    "unlimited": false,
    "total_available": 3,
    "quotes_used": 1,
    "quotes_remaining": 2,
    "additional_quotes": 0
  }
}
```

### POST /api/payments/webhook

Webhook-Endpunkt für Stripe-Events. Wird automatisch von Stripe aufgerufen.

**Headers:**
- `Stripe-Signature`: Webhook-Signatur für Verifizierung

**Response:**
```json
{
  "status": "success"
}
```

## Fehlerbehandlung

Alle API-Endpunkte verwenden standardisierte HTTP-Statuscodes und Fehlerformate:

**Erfolgreiche Responses:** 200 (OK), 201 (Created)
**Client-Fehler:** 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found)
**Server-Fehler:** 500 (Internal Server Error)

**Fehlerformat:**
```json
{
  "success": false,
  "error": "Beschreibung des Fehlers",
  "code": "ERROR_CODE (optional)"
}
```

## Rate Limiting

Die API implementiert Rate Limiting basierend auf dem Benutzer-Kontingent:
- Kostenlose Benutzer: 3 Angebote pro Monat
- Premium-Benutzer: Unbegrenzte Angebote
- API-Requests: 100 Requests pro Minute pro Benutzer

## Versionierung

Die API verwendet URL-basierte Versionierung. Die aktuelle Version ist v1 und wird über den Pfad `/api/v1/` erreicht. Zukünftige Versionen werden als `/api/v2/` etc. bereitgestellt, wobei ältere Versionen für Rückwärtskompatibilität beibehalten werden.

