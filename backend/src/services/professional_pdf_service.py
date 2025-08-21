import os
import io
import base64
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import json
import logging

# Professional PDF imports
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    Image, PageBreak, FrameBreak, KeepTogether, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader

logger = logging.getLogger(__name__)

class ProfessionalPDFService:
    """Enhanced PDF service for professional quote generation with company branding"""
    
    def __init__(self):
        self.company_settings = {
            'name': os.getenv('COMPANY_NAME', 'Maler Mustermann GmbH'),
            'address': os.getenv('COMPANY_ADDRESS', 'Musterstraße 123\n12345 Musterstadt'),
            'phone': os.getenv('COMPANY_PHONE', '+49 123 456789'),
            'email': os.getenv('COMPANY_EMAIL', 'info@maler-mustermann.de'),
            'website': os.getenv('COMPANY_WEBSITE', 'www.maler-mustermann.de'),
            'tax_number': os.getenv('COMPANY_TAX_NUMBER', 'DE123456789'),
            'bank_name': os.getenv('COMPANY_BANK', 'Sparkasse Musterstadt'),
            'iban': os.getenv('COMPANY_IBAN', 'DE89 3705 0198 0000 0001 23'),
            'bic': os.getenv('COMPANY_BIC', 'COLSDE33'),
            'managing_director': os.getenv('COMPANY_MD', 'Max Mustermann'),
            'trade_register': os.getenv('COMPANY_TRADE_REG', 'HRB 12345 Amtsgericht Musterstadt')
        }
        self.brand_colors = {
            'primary': HexColor('#2196F3'),    # Blue
            'secondary': HexColor('#FFC107'),   # Amber
            'accent': HexColor('#4CAF50'),      # Green
            'text_primary': HexColor('#212121'), # Dark grey
            'text_secondary': HexColor('#757575'), # Medium grey
            'background': HexColor('#FAFAFA')   # Light grey
        }
        self.logo_path = os.getenv('COMPANY_LOGO_PATH', 'static/logo.png')
        self.uploads_dir = Path('uploads/pdfs')
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Digital signature settings
        self.signature_path = os.getenv('DIGITAL_SIGNATURE_PATH', 'static/signature.png')
        self.signature_name = os.getenv('SIGNATURE_NAME', self.company_settings['managing_director'])
        self.signature_title = os.getenv('SIGNATURE_TITLE', 'Geschäftsführer')

    async def generate_professional_quote_pdf(self, quote_data: Dict, options: Optional[Dict] = None) -> Dict:
        """
        Generate professional PDF with company branding and digital signature
        """
        try:
            options = options or {}
            filename = f"{quote_data.get('quote_number', 'quote')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            file_path = self.uploads_dir / filename
            
            # Create PDF document with professional settings
            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=3*cm,
                bottomMargin=3*cm,
                title=f"Kostenvoranschlag {quote_data.get('quote_number', '')}",
                author=self.company_settings['name'],
                subject=f"Kostenvoranschlag für {quote_data.get('customer_name', '')}",
                creator="Maler Kostenvoranschlag Generator"
            )
            
            # Build PDF story
            story = []
            styles = self._create_custom_styles()
            
            # Header with logo and company info
            story.extend(self._build_header(quote_data, styles))
            story.append(Spacer(1, 15*mm))
            
            # Quote title and number
            story.extend(self._build_quote_title(quote_data, styles))
            story.append(Spacer(1, 10*mm))
            
            # Customer and quote information
            story.extend(self._build_info_section(quote_data, styles))
            story.append(Spacer(1, 15*mm))
            
            # Quote items table
            story.extend(self._build_items_table(quote_data, styles))
            story.append(Spacer(1, 15*mm))
            
            # Terms and conditions
            story.extend(self._build_terms_section(quote_data, styles))
            story.append(Spacer(1, 10*mm))
            
            # Digital signature
            if options.get('include_signature', True):
                story.extend(self._build_signature_section(styles))
            
            # Footer information
            story.extend(self._build_footer_info(styles))
            
            # Build PDF with custom page template
            doc.build(
                story, 
                onFirstPage=self._create_page_template,
                onLaterPages=self._create_page_template
            )
            
            # Generate download URL and metadata
            file_size = file_path.stat().st_size
            
            result = {
                'success': True,
                'filename': filename,
                'file_path': str(file_path),
                'file_size': file_size,
                'download_url': f"/api/v1/quotes/{quote_data.get('id', 0)}/pdf/download",
                'created_at': datetime.now().isoformat(),
                'quote_number': quote_data.get('quote_number'),
                'customer_name': quote_data.get('customer_name')
            }
            
            logger.info(f"Professional PDF generated: {filename} ({file_size} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Professional PDF generation error: {str(e)}")
            return {
                'success': False,
                'error': f'PDF generation failed: {str(e)}'
            }

    def _create_custom_styles(self):
        """Create custom paragraph styles for professional appearance"""
        styles = getSampleStyleSheet()
        
        # Define all custom styles to add
        custom_styles = {
            'CompanyHeader': ParagraphStyle(
                'CompanyHeader',
                parent=styles['Normal'],
                fontSize=18,
                textColor=self.brand_colors['primary'],
                fontName='Helvetica-Bold',
                alignment=TA_LEFT,
                spaceAfter=5*mm
            ),
            'QuoteTitle': ParagraphStyle(
                'QuoteTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=self.brand_colors['primary'],
                fontName='Helvetica-Bold',
                alignment=TA_CENTER,
                spaceAfter=8*mm,
                spaceBefore=5*mm
            ),
            'SectionHeader': ParagraphStyle(
                'SectionHeader',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=self.brand_colors['text_primary'],
                fontName='Helvetica-Bold',
                alignment=TA_LEFT,
                spaceAfter=3*mm,
                spaceBefore=5*mm,
                borderWidth=0,
                borderColor=self.brand_colors['primary']
            ),
            'BodyText': ParagraphStyle(
                'BodyText',
                parent=styles['Normal'],
                fontSize=10,
                textColor=self.brand_colors['text_primary'],
                fontName='Helvetica',
                alignment=TA_LEFT,
                spaceAfter=2*mm,
                leading=12
            ),
            'TableHeader': ParagraphStyle(
                'TableHeader',
                parent=styles['Normal'],
                fontSize=9,
                textColor=white,
                fontName='Helvetica-Bold',
                alignment=TA_CENTER
            ),
            'Footer': ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=self.brand_colors['text_secondary'],
                fontName='Helvetica',
                alignment=TA_CENTER,
                spaceAfter=2*mm
            )
        }
        
        # Add only styles that don't already exist
        for style_name, style_def in custom_styles.items():
            if style_name not in styles:
                styles.add(style_def)
        
        return styles
    
    def _format_currency(self, amount: float) -> str:
        """Format currency with German locale"""
        # Format: 1.234,56 €
        return f"{amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + " €"
    
    def _calculate_totals(self, quote_items: list) -> Dict:
        """Calculate quote totals including VAT"""
        subtotal = sum(item.get('total_price', 0) for item in quote_items)
        vat_rate = 0.19  # 19% VAT
        vat_amount = subtotal * vat_rate
        total_amount = subtotal + vat_amount
        
        return {
            'subtotal': subtotal,
            'vat_rate': vat_rate,
            'vat_amount': vat_amount,
            'total_amount': total_amount
        }

    def _build_header(self, quote_data: Dict, styles) -> list:
        """Build professional header with logo and company information"""
        elements = []
        
        # Company name and contact info in a table layout
        header_data = [[
            [Paragraph(self.company_settings['name'], styles['CompanyHeader']),
             Paragraph(f"{self.company_settings['address']}", styles['BodyText']),
             Paragraph(f"Tel: {self.company_settings['phone']}", styles['BodyText']),
             Paragraph(f"E-Mail: {self.company_settings['email']}", styles['BodyText']),
             Paragraph(f"Web: {self.company_settings['website']}", styles['BodyText'])]
        ]]
        
        # Try to add logo if available
        try:
            if os.path.exists(self.logo_path):
                header_data[0].append([self._create_logo_image()])
            else:
                # Placeholder for logo
                header_data[0].append([Paragraph("[LOGO]", styles['CompanyHeader'])])
        except Exception:
            header_data[0].append([Paragraph("[LOGO]", styles['CompanyHeader'])])
        
        header_table = Table(header_data, colWidths=[12*cm, 6*cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT')
        ]))
        
        elements.append(header_table)
        return elements
    
    def _build_quote_title(self, quote_data: Dict, styles) -> list:
        """Build quote title section"""
        elements = []
        
        # Main title
        elements.append(Paragraph("KOSTENVORANSCHLAG", styles['QuoteTitle']))
        
        # Quote number and date info
        info_data = [
            ['Angebots-Nr.:', quote_data.get('quote_number', 'N/A'),
             'Datum:', datetime.now().strftime('%d.%m.%Y')],
            ['Gültig bis:', (datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y'),
             'Projekt:', quote_data.get('project_title', 'N/A')]
        ]
        
        info_table = Table(info_data, colWidths=[3*cm, 5*cm, 2*cm, 6*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT')
        ]))
        
        elements.append(info_table)
        return elements
    
    def _build_info_section(self, quote_data: Dict, styles) -> list:
        """Build customer and project information section"""
        elements = []
        
        # Customer information
        elements.append(Paragraph("Kunde:", styles['SectionHeader']))
        customer_info = f"""
        <b>{quote_data.get('customer_name', 'N/A')}</b><br/>
        {quote_data.get('customer_address', '')}<br/>
        {quote_data.get('customer_email', '')}<br/>
        {quote_data.get('customer_phone', '')}
        """
        elements.append(Paragraph(customer_info, styles['BodyText']))
        
        # Project description if available
        if quote_data.get('project_description'):
            elements.append(Spacer(1, 5*mm))
            elements.append(Paragraph("Projektbeschreibung:", styles['SectionHeader']))
            elements.append(Paragraph(quote_data['project_description'], styles['BodyText']))
        
        return elements
    
    def _build_items_table(self, quote_data: Dict, styles) -> list:
        """Build professional items table with totals"""
        elements = []
        
        elements.append(Paragraph("Leistungen:", styles['SectionHeader']))
        
        # Table headers
        table_data = [[
            Paragraph('Pos.', styles['TableHeader']),
            Paragraph('Beschreibung', styles['TableHeader']),
            Paragraph('Menge', styles['TableHeader']),
            Paragraph('Einheit', styles['TableHeader']),
            Paragraph('Einzelpreis', styles['TableHeader']),
            Paragraph('Gesamtpreis', styles['TableHeader'])
        ]]
        
        # Quote items
        quote_items = quote_data.get('items', quote_data.get('quote_items', []))
        for item in quote_items:
            table_data.append([
                str(item.get('position', '')),
                item.get('description', ''),
                f"{item.get('quantity', 0):.1f}",
                item.get('unit', ''),
                self._format_currency(item.get('unit_price', 0)),
                self._format_currency(item.get('total_price', 0))
            ])
        
        # Calculate totals
        totals = self._calculate_totals(quote_items)
        
        # Add spacing row
        table_data.append(['', '', '', '', '', ''])
        
        # Add totals
        table_data.extend([
            ['', '', '', '', 'Zwischensumme:', self._format_currency(totals['subtotal'])],
            ['', '', '', '', f"MwSt. ({totals['vat_rate']*100:.0f}%):", self._format_currency(totals['vat_amount'])],
            ['', '', '', '', 'Gesamtsumme:', self._format_currency(totals['total_amount'])]
        ])
        
        # Create table
        table = Table(table_data, colWidths=[1*cm, 7*cm, 2*cm, 2*cm, 3*cm, 3*cm])
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), self.brand_colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8*mm),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -4), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -4), 9),
            ('GRID', (0, 0), (-1, -4), 1, grey),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Position column
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),   # Quantity column
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),  # Price columns
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Totals styling
            ('FONTNAME', (4, -3), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (4, -1), (-1, -1), HexColor('#E3F2FD')),
            ('FONTSIZE', (4, -1), (-1, -1), 11),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -4), [white, HexColor('#F5F5F5')])
        ]))
        
        elements.append(table)
        return elements
    
    def _build_terms_section(self, quote_data: Dict, styles) -> list:
        """Build terms and conditions section"""
        elements = []
        
        elements.append(Paragraph("Konditionen:", styles['SectionHeader']))
        
        terms_text = f"""
        <b>Zahlungsbedingungen:</b> 30 Tage netto nach Rechnungsstellung<br/>
        <b>Gewährleistung:</b> 2 Jahre Gewährleistung auf Malerarbeiten gemäß VOB/B<br/>
        <b>Gültigkeitsdauer:</b> Dieses Angebot ist 30 Tage ab Angebotsdatum gültig<br/>
        <b>Ausführung:</b> Nach Auftragserteilung und Terminabsprache<br/><br/>
        
        <b>Hinweise:</b><br/>
        • Alle Preise verstehen sich inklusive der gesetzlichen Mehrwertsteuer<br/>
        • Eventuelle Gerüstkosten sind nicht enthalten und werden separat berechnet<br/>
        • Änderungen und Zusatzarbeiten werden nach Aufwand abgerechnet<br/>
        • Bei Auftragserteilung gelten unsere allgemeinen Geschäftsbedingungen
        """
        
        elements.append(Paragraph(terms_text, styles['BodyText']))
        return elements
    
    def _build_signature_section(self, styles) -> list:
        """Build digital signature section"""
        elements = []
        
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph("Mit freundlichen Grüßen", styles['BodyText']))
        
        # Try to add signature image
        try:
            if os.path.exists(self.signature_path):
                signature_img = Image(self.signature_path, width=4*cm, height=2*cm)
                elements.append(signature_img)
            else:
                elements.append(Spacer(1, 2*cm))  # Space for manual signature
        except Exception:
            elements.append(Spacer(1, 2*cm))  # Space for manual signature
        
        # Signature details
        signature_text = f"""
        <b>{self.signature_name}</b><br/>
        {self.signature_title}<br/>
        {self.company_settings['name']}
        """
        elements.append(Paragraph(signature_text, styles['BodyText']))
        
        return elements
    
    def _build_footer_info(self, styles) -> list:
        """Build footer with company details"""
        elements = []
        
        elements.append(Spacer(1, 10*mm))
        
        # Company details in small print
        footer_text = f"""
        <b>{self.company_settings['name']}</b> • 
        {self.company_settings['address'].replace(chr(10), ' • ')}<br/>
        Geschäftsführer: {self.company_settings['managing_director']} • 
        {self.company_settings['trade_register']}<br/>
        Steuernummer: {self.company_settings['tax_number']} • 
        Bank: {self.company_settings['bank_name']}<br/>
        IBAN: {self.company_settings['iban']} • BIC: {self.company_settings['bic']}
        """
        
        elements.append(Paragraph(footer_text, styles['Footer']))
        return elements
    
    def _create_logo_image(self) -> Image:
        """Create logo image with proper sizing"""
        return Image(self.logo_path, width=4*cm, height=2*cm)
    
    def _create_page_template(self, canvas_obj, doc):
        """Create custom page template with header and footer"""
        canvas_obj.saveState()
        
        # Page number
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(self.brand_colors['text_secondary'])
        canvas_obj.drawRightString(
            A4[0] - 2*cm, 
            1*cm, 
            f"Seite {doc.page}"
        )
        
        canvas_obj.restoreState()

# Export service for different formats
class QuoteExportService:
    """Service for exporting quotes in different formats"""
    
    def __init__(self):
        self.pdf_service = ProfessionalPDFService()
    
    async def export_quote(self, quote_data: Dict, format_type: str = 'pdf', options: Dict = None) -> Dict:
        """Export quote in specified format"""
        options = options or {}
        
        if format_type.lower() == 'pdf':
            return await self.pdf_service.generate_professional_quote_pdf(quote_data, options)
        elif format_type.lower() == 'json':
            return self._export_json(quote_data)
        elif format_type.lower() == 'csv':
            return self._export_csv(quote_data)
        else:
            return {
                'success': False,
                'error': f'Unsupported export format: {format_type}'
            }
    
    def _export_json(self, quote_data: Dict) -> Dict:
        """Export quote as JSON"""
        try:
            filename = f"{quote_data.get('quote_number', 'quote')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = Path('uploads/exports') / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(quote_data, f, indent=2, ensure_ascii=False, default=str)
            
            return {
                'success': True,
                'filename': filename,
                'file_path': str(file_path),
                'format': 'json'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'JSON export failed: {str(e)}'
            }
    
    def _export_csv(self, quote_data: Dict) -> Dict:
        """Export quote items as CSV"""
        try:
            import csv
            
            filename = f"{quote_data.get('quote_number', 'quote')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path = Path('uploads/exports') / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            quote_items = quote_data.get('items', quote_data.get('quote_items', []))
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')  # German CSV format
                
                # Headers
                writer.writerow([
                    'Position', 'Beschreibung', 'Menge', 'Einheit', 
                    'Einzelpreis', 'Gesamtpreis', 'Raum'
                ])
                
                # Items
                for item in quote_items:
                    writer.writerow([
                        item.get('position', ''),
                        item.get('description', ''),
                        item.get('quantity', 0),
                        item.get('unit', ''),
                        item.get('unit_price', 0),
                        item.get('total_price', 0),
                        item.get('room_name', '')
                    ])
            
            return {
                'success': True,
                'filename': filename,
                'file_path': str(file_path),
                'format': 'csv'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'CSV export failed: {str(e)}'
            }