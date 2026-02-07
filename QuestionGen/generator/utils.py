import logging
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

logger = logging.getLogger(__name__)

# Register a Unicode-compatible font
def register_unicode_fonts():
    try:
        # Try fonts with good Unicode/symbol support (in order of preference)
        font_paths = [
            ("C:/Windows/Fonts/seguisym.ttf", "SegoeSymbol"),  # Best for symbols
            ("C:/Windows/Fonts/segoeui.ttf", "SegoeUI"),
            ("C:/Windows/Fonts/arial.ttf", "Arial"),
        ]
        registered_fonts = []
        for font_path, font_name in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    registered_fonts.append(font_name)
                except Exception as e:
                    logger.warning(f"Could not register font {font_name}: {e}")
        
        return registered_fonts[0] if registered_fonts else 'Helvetica'
    except Exception as e:
        logger.warning(f"Could not register Unicode font: {e}")
    return 'Helvetica'

UNICODE_FONT = register_unicode_fonts()

def sanitize_text_for_pdf(text):
    """Convert Unicode symbols to PDF-safe representations"""
    replacements = {
        # Subscripts to regular numbers with underscore notation
        '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
        '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
        # Superscripts - keep common ones, convert others
        '⁺': '+', '⁻': '-',
        # Quantum notation
        '⟩': '>', '⟨': '<',
        '|ψ⟩': '|psi>', '|φ⟩': '|phi>',
        '⊗': ' (tensor) ', '⊕': ' (xor) ',
        # Greek letters - spell out if font doesn't support
        'ψ': 'psi', 'Ψ': 'Psi',
        'φ': 'phi', 'Φ': 'Phi', 
        'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta',
        'ε': 'epsilon', 'θ': 'theta', 'λ': 'lambda', 'μ': 'mu',
        'σ': 'sigma', 'ω': 'omega', 'π': 'pi',
        # Math symbols
        '√': 'sqrt', '∛': 'cbrt',
        '∑': 'Sum', '∫': 'Int', '∂': 'd',
        '∇': 'nabla', '∞': 'infinity',
        '≠': '!=', '≤': '<=', '≥': '>=', '≈': '~=', '≡': '==',
        '±': '+/-', '×': 'x', '÷': '/',
        '→': '->', '←': '<-', '↔': '<->', '⇒': '=>', '⇐': '<=', '⇔': '<=>',
        # Fractions
        '½': '1/2', '⅓': '1/3', '¼': '1/4', '⅔': '2/3', '¾': '3/4',
    }
    
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    
    return text

def generate_pdf_file(questions, topic, include_answers=True):
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#00d4ff'),
            spaceAfter=30,
            alignment=0
        )
        
        question_style = ParagraphStyle(
            'CustomQuestion',
            parent=styles['BodyText'],
            fontSize=11,
            textColor=colors.black,
            spaceAfter=6,
            leading=16,
            fontName=UNICODE_FONT
        )
        
        option_style = ParagraphStyle(
            'CustomOption',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=3,
            leading=14,
            leftIndent=20,
            fontName=UNICODE_FONT
        )
        
        answer_style = ParagraphStyle(
            'CustomAnswer',
            parent=styles['Italic'],
            fontSize=10,
            textColor=colors.HexColor('#2d5016'),
            spaceAfter=12,
            leading=14,
            leftIndent=20,
            fontName=UNICODE_FONT
        )
        
        story = []
        
        label = "Questions & Answers" if include_answers else "Questions Only"
        title_text = f"{topic} - {label}"
        title_p = Paragraph(title_text, title_style)
        story.append(title_p)
        story.append(Spacer(1, 0.3*inch))
        
        for i, q in enumerate(questions, 1):
            q_text = sanitize_text_for_pdf(q.text).replace('\n', '<br/>')
            question_text = f"<b>{i}. {q_text}</b>"
            question_p = Paragraph(question_text, question_style)
            story.append(question_p)
            story.append(Spacer(1, 0.1*inch))
            
            if include_answers and q.answer:
                answer_text = sanitize_text_for_pdf(q.answer).replace('\n', '<br/>')
                answer_p = Paragraph(f"<b>Answer:</b> {answer_text}", answer_style)
                story.append(answer_p)
            
            story.append(Spacer(1, 0.3*inch))
            
            q_type = getattr(q, 'question_type', 'SHORT')
            if q_type in ['MCQ', 'TF']:
                if (i % 2 == 0) and (i < len(questions)):
                    story.append(PageBreak())
            elif (i % 4 == 0) and (i < len(questions)):
                story.append(PageBreak())
        
        doc.build(story)
        
        buffer.seek(0)
        logger.info(f"PDF generated ({'with' if include_answers else 'without'} answers): {len(buffer.getvalue())} bytes")
        return buffer
        
    except Exception as e:
        logger.error(f"Error in generate_pdf_file: {str(e)}", exc_info=True)
        raise


def generate_notes_pdf(notes_text, title):
    """Generate a PDF from short notes text"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
        
        styles = getSampleStyleSheet()
        
        # Custom styles for notes
        title_style = ParagraphStyle(
            'NotesTitle',
            parent=styles['Heading1'],
            fontSize=22,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=20,
            alignment=1,
            fontName=UNICODE_FONT
        )
        
        heading_style = ParagraphStyle(
            'NotesHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e40af'),
            spaceBefore=15,
            spaceAfter=8,
            fontName=UNICODE_FONT,
            borderWidth=0,
            borderPadding=0,
            borderColor=colors.HexColor('#3b82f6'),
            borderRadius=0,
        )
        
        subheading_style = ParagraphStyle(
            'NotesSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#374151'),
            spaceBefore=10,
            spaceAfter=5,
            fontName=UNICODE_FONT
        )
        
        body_style = ParagraphStyle(
            'NotesBody',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=6,
            leading=14,
            fontName=UNICODE_FONT
        )
        
        bullet_style = ParagraphStyle(
            'NotesBullet',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor('#374151'),
            spaceAfter=4,
            leading=13,
            leftIndent=15,
            fontName=UNICODE_FONT
        )
        
        key_point_style = ParagraphStyle(
            'KeyPoint',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor('#dc2626'),
            spaceAfter=4,
            leading=13,
            leftIndent=15,
            fontName=UNICODE_FONT
        )
        
        formula_style = ParagraphStyle(
            'Formula',
            parent=styles['BodyText'],
            fontSize=11,
            textColor=colors.HexColor('#7c3aed'),
            spaceAfter=6,
            leading=14,
            leftIndent=20,
            fontName=UNICODE_FONT,
            backColor=colors.HexColor('#f3f4f6'),
        )
        
        tip_style = ParagraphStyle(
            'Tip',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor('#059669'),
            spaceAfter=6,
            leading=13,
            leftIndent=15,
            fontName=UNICODE_FONT
        )
        
        story = []
        
        # Sanitize the notes text first to convert Unicode to readable ASCII
        notes_text = sanitize_text_for_pdf(notes_text)
        
        # Add title
        story.append(Paragraph(f"Short Notes: {title}", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Parse and format the notes
        lines = notes_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.1*inch))
                continue
            
            # Escape special XML characters
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Remove emoji characters that might not render
            import re
            line = re.sub(r'[^\x00-\x7F\u00C0-\u017F]+', '', line).strip()
            
            if not line:
                continue
            
            # Determine line type and apply appropriate style
            if line.startswith('## '):
                # Main heading
                text = line[3:].strip()
                story.append(Paragraph(f"<b>{text}</b>", heading_style))
            elif line.startswith('### '):
                # Subheading
                text = line[4:].strip()
                story.append(Paragraph(f"<b>{text}</b>", subheading_style))
            elif 'KEY POINT' in line.upper() or line.startswith('**'):
                # Key point
                text = line.replace('**', '').strip()
                story.append(Paragraph(f"<b>{text}</b>", key_point_style))
            elif 'FORMULA' in line.upper():
                # Formula
                text = line.strip()
                story.append(Paragraph(text, formula_style))
            elif 'TIP' in line.upper():
                # Tip
                text = line.strip()
                story.append(Paragraph(f"<i>{text}</i>", tip_style))
            elif line.startswith('*') or line.startswith('-') or line.startswith('-&gt;'):
                # Bullet point
                if line.startswith('-&gt;'):
                    line = '-> ' + line[5:].strip()
                story.append(Paragraph(line, bullet_style))
            elif line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                # Numbered list
                story.append(Paragraph(line, bullet_style))
            else:
                # Regular text
                story.append(Paragraph(line, body_style))
        
        doc.build(story)
        
        buffer.seek(0)
        logger.info(f"Notes PDF generated: {len(buffer.getvalue())} bytes")
        return buffer
        
    except Exception as e:
        logger.error(f"Error in generate_notes_pdf: {str(e)}", exc_info=True)
        raise