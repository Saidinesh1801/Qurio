from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO

def generate_pdf_file(questions, topic):
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
        
        styles = getSampleStyleSheet()
        
        # Create custom styles
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
            leading=14,
            fontName='Helvetica-Bold'
        )
        
        answer_style = ParagraphStyle(
            'CustomAnswer',
            parent=styles['Italic'],
            fontSize=10,
            textColor=colors.HexColor('#2d5016'),
            spaceAfter=12,
            leading=13,
            leftIndent=20,
            fontName='Helvetica'
        )
        
        story = []
        
        # Add title
        title_text = f"Generated Questions: {topic}"
        title_p = Paragraph(title_text, title_style)
        story.append(title_p)
        story.append(Spacer(1, 0.3*inch))
        
        # Add questions
        for i, q in enumerate(questions, 1):
            # Question without marks
            question_text = f"<b>{i}. {q.text}</b>"
            question_p = Paragraph(question_text, question_style)
            story.append(question_p)
            story.append(Spacer(1, 0.08*inch))
            
            # Answer - with label
            if q.answer:
                answer_text = f"<b>Answer:</b> {q.answer}"
                answer_p = Paragraph(answer_text, answer_style)
                story.append(answer_p)
            
            story.append(Spacer(1, 0.25*inch))
            
            # Add page break after every 3 questions
            if (i % 3 == 0) and (i < len(questions)):
                story.append(PageBreak())
        
        # Build the document
        doc.build(story)
        
        buffer.seek(0)
        print(f"DEBUG: PDF buffer size: {len(buffer.getvalue())} bytes")
        return buffer
        
    except Exception as e:
        print(f"ERROR in generate_pdf_file: {str(e)}")
        import traceback
        traceback.print_exc()
        raise