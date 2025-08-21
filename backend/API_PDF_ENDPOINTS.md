# Professional PDF Generation API Endpoints

## Story 3.1.1 - Professional PDF Generation (8 SP) - COMPLETED ✅

### Endpoints

#### 1. Generate Professional PDF
```
POST /api/v1/quotes/{quote_id}/pdf/generate
```

**Request Body:**
```json
{
  "include_signature": true,
  "include_logo": true,
  "include_terms": true,
  "custom_footer": "Optional custom footer text"
}
```

**Response:**
```json
{
  "success": true,
  "message": "PDF generated successfully",
  "pdf_info": {
    "filename": "KV-20250821-143000_20250821_174300.pdf",
    "file_path": "uploads/pdfs/KV-20250821-143000_20250821_174300.pdf",
    "file_size": 4936,
    "download_url": "/api/v1/quotes/1/pdf/download",
    "created_at": "2025-08-21T17:43:00.123456",
    "quote_number": "KV-20250821-143000",
    "customer_name": "Mustermann GmbH"
  }
}
```

#### 2. Download Generated PDF
```
GET /api/v1/quotes/{quote_id}/pdf/download
```

**Response:** PDF file download (Content-Type: application/pdf)

#### 3. Export Quote (Multiple Formats)
```
POST /api/v1/quotes/{quote_id}/export
```

**Request Body:**
```json
{
  "format_type": "pdf",  // "pdf", "json", "csv"
  "include_signature": true,
  "include_logo": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Quote exported as PDF successfully",
  "export_info": {
    "filename": "KV-20250821-143000_20250821_174300.pdf",
    "file_path": "uploads/pdfs/KV-20250821-143000_20250821_174300.pdf",
    "file_size": 4936,
    "format": "pdf"
  }
}
```

### Features Implemented

✅ **Company Branding Integration:**
- Company logo placeholder
- Professional color scheme (Blue primary, Amber secondary)
- Corporate header with contact information
- Company footer with legal details (tax number, bank info, etc.)

✅ **Professional Layout:**
- Professional A4 document format
- Custom typography and spacing
- Branded header and footer
- Clean table design with alternating row colors
- German locale formatting for dates and currency

✅ **Itemized Costs:**
- Professional cost breakdown table
- Position, description, quantity, unit, unit price, total price columns
- Subtotal, VAT (19%), and total amount calculations
- German currency formatting (1.234,56 €)
- Room-specific item grouping

✅ **Digital Signatures:**
- Digital signature placeholder section
- Configurable signature inclusion
- Signature details (name, title, company)
- Professional closing ("Mit freundlichen Grüßen")

✅ **Export Options:**
- PDF export with professional formatting
- JSON export for data integration
- CSV export for spreadsheet compatibility
- Configurable export options (signature, logo, terms)

### Technical Implementation

- **ProfessionalPDFService:** Main PDF generation service with ReportLab
- **QuoteExportService:** Multi-format export service
- **Custom Styles:** Professional typography with brand colors
- **Template System:** Modular PDF sections (header, items, terms, signature, footer)
- **File Management:** Organized uploads directory with automatic cleanup
- **Error Handling:** Comprehensive error handling with user-friendly messages

### Environment Variables

```env
COMPANY_NAME=Maler Mustermann GmbH
COMPANY_ADDRESS=Musterstraße 123\n12345 Musterstadt
COMPANY_PHONE=+49 123 456789
COMPANY_EMAIL=info@maler-mustermann.de
COMPANY_WEBSITE=www.maler-mustermann.de
COMPANY_TAX_NUMBER=DE123456789
COMPANY_BANK=Sparkasse Musterstadt
COMPANY_IBAN=DE89 3705 0198 0000 0001 23
COMPANY_BIC=COLSDE33
COMPANY_MD=Max Mustermann
COMPANY_TRADE_REG=HRB 12345 Amtsgericht Musterstadt
COMPANY_LOGO_PATH=static/logo.png
DIGITAL_SIGNATURE_PATH=static/signature.png
SIGNATURE_NAME=Max Mustermann
SIGNATURE_TITLE=Geschäftsführer
```

### Generated Files Location

- **PDFs:** `uploads/pdfs/`
- **JSON Exports:** `uploads/exports/`
- **CSV Exports:** `uploads/exports/`

All files are automatically timestamped and organized by quote number for easy management.