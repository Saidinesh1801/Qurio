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
            spaceAfter=6,
            leading=13,
            leftIndent=20,
            fontName='Helvetica'
        )
        
        explanation_style = ParagraphStyle(
            'CustomExplanation',
            parent=styles['BodyText'],
            fontSize=9,
            textColor=colors.HexColor('#1a4d7c'),
            spaceAfter=12,
            leading=12,
            leftIndent=20,
            fontName='Helvetica',
            backColor=colors.HexColor('#f0f7ff'),
            borderPadding=8
        )
        
        step_style = ParagraphStyle(
            'StepStyle',
            parent=styles['BodyText'],
            fontSize=9,
            textColor=colors.HexColor('#333333'),
            spaceAfter=3,
            leading=11,
            leftIndent=30,
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
            # Question with type indicator for numerical problems
            q_type = getattr(q, 'question_type', 'mixed')
            type_label = " [Numerical]" if q_type == 'numerical' else ""
            question_text = f"<b>{i}. {q.text}{type_label}</b>"
            question_p = Paragraph(question_text, question_style)
            story.append(question_p)
            story.append(Spacer(1, 0.08*inch))
            
            # Answer - with label
            if q.answer:
                answer_text = f"<b>Answer:</b> {q.answer}"
                answer_p = Paragraph(answer_text, answer_style)
                story.append(answer_p)
            
            # Step-by-step explanation for numerical problems
            explanation = getattr(q, 'explanation', '')
            if explanation:
                story.append(Spacer(1, 0.05*inch))
                explanation_header = Paragraph("<b>Step-by-Step Solution:</b>", explanation_style)
                story.append(explanation_header)
                
                # Parse and format steps
                steps = explanation.replace('Step ', '\nStep ').strip().split('\n')
                for step in steps:
                    step = step.strip()
                    if step:
                        step_p = Paragraph(step, step_style)
                        story.append(step_p)
            
            story.append(Spacer(1, 0.25*inch))
            
            # Add page break after every 2 questions (numerical problems take more space)
            questions_per_page = 2 if q_type == 'numerical' else 3
            if (i % questions_per_page == 0) and (i < len(questions)):
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