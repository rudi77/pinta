import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from jinja2 import Template
import json

class PDFService:
    def __init__(self):
        self.craftmypdf_api_key = os.getenv('CRAFTMYPDF_API_KEY')
        self.craftmypdf_template_id = os.getenv('CRAFTMYPDF_TEMPLATE_ID')
        self.base_url = 'https://api.craftmypdf.com/v1'
    
    def generate_quote_pdf(self, quote_data):
        """
        Generate PDF using CraftMyPDF API
        """
        try:
            # Prepare data for PDF template
            pdf_data = self._prepare_pdf_data(quote_data)
            
            # Make API request to CraftMyPDF
            headers = {
                'X-API-KEY': self.craftmypdf_api_key,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'template_id': self.craftmypdf_template_id,
                'data': pdf_data,
                'export_type': 'pdf',
                'expiration': 60  # PDF expires in 60 minutes
            }
            
            response = requests.post(
                f'{self.base_url}/create',
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'pdf_url': result.get('file'),
                    'download_url': result.get('file'),
                    'expires_at': result.get('expires_at')
                }
            else:
                return {
                    'success': False,
                    'error': f'PDF generation failed: {response.text}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'PDF generation error: {str(e)}'
            }
    
    def _prepare_pdf_data(self, quote_data):
        """
        Prepare quote data for PDF template
        """
        # Format currency
        def format_currency(amount):
            return f"{amount:,.2f} €".replace(',', '.')
        
        # Calculate totals
        subtotal = sum(item['total_price'] for item in quote_data['quote_items'])
        vat_rate = 0.19  # 19% VAT
        vat_amount = subtotal * vat_rate
        total_amount = subtotal + vat_amount
        
        return {
            # Quote information
            'quote_number': quote_data['quote_number'],
            'quote_date': datetime.now().strftime('%d.%m.%Y'),
            'valid_until': (datetime.now().replace(day=datetime.now().day + 30)).strftime('%d.%m.%Y'),
            
            # Customer information
            'customer_name': quote_data['customer_name'],
            'customer_email': quote_data.get('customer_email', ''),
            'customer_phone': quote_data.get('customer_phone', ''),
            'customer_address': quote_data.get('customer_address', ''),
            
            # Project information
            'project_title': quote_data['project_title'],
            'project_description': quote_data.get('project_description', ''),
            
            # Quote items
            'quote_items': [
                {
                    'position': item['position'],
                    'description': item['description'],
                    'quantity': f"{item['quantity']:.1f}",
                    'unit': item['unit'],
                    'unit_price': format_currency(item['unit_price']),
                    'total_price': format_currency(item['total_price']),
                    'room_name': item.get('room_name', '')
                }
                for item in quote_data['quote_items']
            ],
            
            # Totals
            'subtotal': format_currency(subtotal),
            'vat_rate': f"{vat_rate * 100:.0f}%",
            'vat_amount': format_currency(vat_amount),
            'total_amount': format_currency(total_amount),
            
            # Company information (from environment or config)
            'company_name': os.getenv('COMPANY_NAME', 'Ihr Malerbetrieb'),
            'company_address': os.getenv('COMPANY_ADDRESS', 'Musterstraße 123\n12345 Musterstadt'),
            'company_phone': os.getenv('COMPANY_PHONE', '+49 123 456789'),
            'company_email': os.getenv('COMPANY_EMAIL', 'info@malerbetrieb.de'),
            'company_website': os.getenv('COMPANY_WEBSITE', 'www.malerbetrieb.de'),
            'company_tax_number': os.getenv('COMPANY_TAX_NUMBER', 'DE123456789'),
            
            # Terms and conditions
            'payment_terms': '30 Tage netto',
            'warranty_terms': '2 Jahre Gewährleistung auf Malerarbeiten',
            'notes': 'Alle Preise verstehen sich zzgl. der gesetzlichen Mehrwertsteuer.'
        }

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_username)
        self.from_name = os.getenv('FROM_NAME', 'Ihr Malerbetrieb')
    
    def send_quote_email(self, quote_data, pdf_url=None):
        """
        Send quote email to customer
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = quote_data['customer_email']
            msg['Subject'] = f"Kostenvoranschlag {quote_data['quote_number']} - {quote_data['project_title']}"
            
            # Email body
            email_body = self._generate_email_body(quote_data)
            msg.attach(MIMEText(email_body, 'html', 'utf-8'))
            
            # Attach PDF if available
            if pdf_url:
                try:
                    pdf_response = requests.get(pdf_url)
                    if pdf_response.status_code == 200:
                        pdf_attachment = MIMEApplication(pdf_response.content, _subtype='pdf')
                        pdf_attachment.add_header(
                            'Content-Disposition', 
                            'attachment', 
                            filename=f"{quote_data['quote_number']}.pdf"
                        )
                        msg.attach(pdf_attachment)
                except Exception as e:
                    print(f"Warning: Could not attach PDF: {e}")
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return {
                'success': True,
                'message': 'Email sent successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Email sending failed: {str(e)}'
            }
    
    def _generate_email_body(self, quote_data):
        """
        Generate HTML email body
        """
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
                .content { margin: 20px 0; }
                .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }
                .highlight { background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 15px 0; }
                .button { 
                    display: inline-block; 
                    padding: 12px 24px; 
                    background-color: #2196f3; 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 10px 0;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Kostenvoranschlag {{ quote_number }}</h2>
                <p>{{ project_title }}</p>
            </div>
            
            <div class="content">
                <p>Sehr geehrte/r {{ customer_name }},</p>
                
                <p>vielen Dank für Ihre Anfrage. Gerne übersenden wir Ihnen hiermit unseren Kostenvoranschlag für das Projekt "{{ project_title }}".</p>
                
                <div class="highlight">
                    <h3>Projektdetails:</h3>
                    <ul>
                        <li><strong>Angebotsnummer:</strong> {{ quote_number }}</li>
                        <li><strong>Projekt:</strong> {{ project_title }}</li>
                        <li><strong>Gesamtsumme:</strong> {{ total_amount }} (inkl. MwSt.)</li>
                        <li><strong>Gültig bis:</strong> {{ valid_until }}</li>
                    </ul>
                </div>
                
                <p>Den detaillierten Kostenvoranschlag finden Sie im Anhang als PDF-Datei.</p>
                
                <p>Bei Fragen stehen wir Ihnen gerne zur Verfügung. Wir freuen uns auf Ihre Rückmeldung und die Zusammenarbeit mit Ihnen.</p>
                
                <p>Mit freundlichen Grüßen<br>
                {{ company_name }}</p>
            </div>
            
            <div class="footer">
                <p>{{ company_name }}<br>
                {{ company_address }}<br>
                Tel: {{ company_phone }}<br>
                E-Mail: {{ company_email }}</p>
                
                <p><small>Diese E-Mail wurde automatisch generiert. Bei Fragen antworten Sie bitte direkt auf diese E-Mail.</small></p>
            </div>
        </body>
        </html>
        """
        
        template = Template(template_str)
        
        # Calculate total amount
        subtotal = sum(item['total_price'] for item in quote_data['quote_items'])
        vat_amount = subtotal * 0.19
        total_amount = subtotal + vat_amount
        
        return template.render(
            quote_number=quote_data['quote_number'],
            customer_name=quote_data['customer_name'],
            project_title=quote_data['project_title'],
            total_amount=f"{total_amount:,.2f} €".replace(',', '.'),
            valid_until=(datetime.now().replace(day=datetime.now().day + 30)).strftime('%d.%m.%Y'),
            company_name=os.getenv('COMPANY_NAME', 'Ihr Malerbetrieb'),
            company_address=os.getenv('COMPANY_ADDRESS', 'Musterstraße 123, 12345 Musterstadt'),
            company_phone=os.getenv('COMPANY_PHONE', '+49 123 456789'),
            company_email=os.getenv('COMPANY_EMAIL', 'info@malerbetrieb.de')
        )

# Alternative: Simple PDF generation using reportlab (fallback)
class SimplePDFService:
    def __init__(self):
        pass
    
    def generate_simple_pdf(self, quote_data, output_path):
        """
        Generate simple PDF using reportlab as fallback
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            
            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor('#2196f3')
            )
            story.append(Paragraph("KOSTENVORANSCHLAG", title_style))
            story.append(Spacer(1, 20))
            
            # Quote info
            quote_info = f"""
            <b>Angebotsnummer:</b> {quote_data['quote_number']}<br/>
            <b>Datum:</b> {datetime.now().strftime('%d.%m.%Y')}<br/>
            <b>Projekt:</b> {quote_data['project_title']}<br/>
            """
            story.append(Paragraph(quote_info, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Customer info
            customer_info = f"""
            <b>Kunde:</b><br/>
            {quote_data['customer_name']}<br/>
            {quote_data.get('customer_address', '')}<br/>
            {quote_data.get('customer_email', '')}<br/>
            {quote_data.get('customer_phone', '')}
            """
            story.append(Paragraph(customer_info, styles['Normal']))
            story.append(Spacer(1, 30))
            
            # Quote items table
            table_data = [['Pos.', 'Beschreibung', 'Menge', 'Einheit', 'Einzelpreis', 'Gesamtpreis']]
            
            for item in quote_data['quote_items']:
                table_data.append([
                    str(item['position']),
                    item['description'],
                    f"{item['quantity']:.1f}",
                    item['unit'],
                    f"{item['unit_price']:.2f} €",
                    f"{item['total_price']:.2f} €"
                ])
            
            # Calculate totals
            subtotal = sum(item['total_price'] for item in quote_data['quote_items'])
            vat_amount = subtotal * 0.19
            total_amount = subtotal + vat_amount
            
            # Add totals
            table_data.append(['', '', '', '', 'Zwischensumme:', f"{subtotal:.2f} €"])
            table_data.append(['', '', '', '', 'MwSt. (19%):', f"{vat_amount:.2f} €"])
            table_data.append(['', '', '', '', 'Gesamtsumme:', f"{total_amount:.2f} €"])
            
            table = Table(table_data, colWidths=[1*cm, 6*cm, 2*cm, 2*cm, 3*cm, 3*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 30))
            
            # Terms
            terms = """
            <b>Zahlungsbedingungen:</b> 30 Tage netto<br/>
            <b>Gewährleistung:</b> 2 Jahre auf Malerarbeiten<br/>
            <b>Gültigkeit:</b> 30 Tage ab Angebotsdatum<br/><br/>
            Alle Preise verstehen sich zzgl. der gesetzlichen Mehrwertsteuer.
            """
            story.append(Paragraph(terms, styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            return {
                'success': True,
                'pdf_path': output_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'PDF generation failed: {str(e)}'
            }

