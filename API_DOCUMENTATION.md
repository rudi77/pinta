# API-Dokumentation

**KI-gestützter Kostenvoranschlags-Generator für Malerbetriebe**

**Version:** 1.0  
**Base URL:** `http://localhost:5000/api`  
**Autor:** Manus AI

---

## Übersicht

Die REST API des Kostenvoranschlags-Systems bietet vollständige Funktionalität für die Verwaltung von Benutzern, Angeboten, KI-Verarbeitung und Zahlungen. Alle Endpunkte folgen RESTful-Prinzipien und verwenden JSON für Request- und Response-Daten.

## Authentifizierung

Die API verwendet JWT-Token für die Authentifizierung. Tokens werden über den `/api/auth/login` Endpunkt bezogen und müssen in allen geschützten Requests im Authorization-Header übertragen werden:

```
Authorization: Bearer <jwt_token>
```

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

