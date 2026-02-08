import os
import logging
import zipfile
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
import json
import base64
import re
from io import BytesIO
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.core.paginator import Paginator
from .utils import generate_pdf_file, generate_notes_pdf
from .models import Question
from .validators import validate_file, validate_num_questions, validate_difficulty, validate_question_type, ValidationError

# Setup logging
logger = logging.getLogger(__name__)

# Setup Gemini
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

api_key = os.environ.get('GEMINI_API_KEY')
if api_key:
    genai.configure(api_key=api_key)
else:
    logger.warning("GEMINI_API_KEY environment variable not set")

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_docx(docx_file):
    """Extract text from uploaded DOCX file"""
    try:
        from docx import Document
        doc = Document(docx_file)
        return "\n".join([para.text for para in doc.paragraphs])
    except ImportError:
        logger.error("python-docx not installed")
        raise

def extract_text_from_txt(txt_file):
    """Extract text from uploaded TXT file"""
    return txt_file.read().decode('utf-8')

def extract_text(file, extension):
    """Extract text based on file type"""
    if extension == '.pdf':
        return extract_text_from_pdf(file)
    elif extension == '.docx':
        return extract_text_from_docx(file)
    elif extension == '.txt':
        return extract_text_from_txt(file)
    else:
        raise ValueError(f"Unsupported file type: {extension}")

def get_question_type_prompt(question_type):
    """Get prompt instructions based on question type"""
    prompts = {
        'MCQ': """Generate Multiple Choice Questions. 
            CRITICAL: You MUST include exactly 4 options (A, B, C, D) as part of the question field.
            
            Example format for the "question" field:
            "What is the capital of France?\nA) London\nB) Paris\nC) Berlin\nD) Madrid"
            
            Use \\n (newline) to separate the question from options and between each option.
            The "answer" field should only contain: "B) Paris" """,
        'TF': """Generate True/False questions.
            CRITICAL: You MUST include the True/False options as part of the question field.
            
            Example format for the "question" field:
            "The Earth is flat.\nA) True\nB) False"
            
            Use \\n (newline) to separate the statement from options.
            The "answer" field should contain: "B) False - The Earth is approximately spherical." """,
        'SHORT': """Generate short answer questions that can be answered in 1-3 sentences.""",
        'LONG': """Generate descriptive/essay questions that require detailed explanations (5-10 sentences).""",
        'NUMERICAL': """Generate NUMERICAL/MATHEMATICAL problems with step-by-step solutions.
            
            Each problem must involve calculations, formulas, or mathematical reasoning.
            
            The answer MUST include a complete step-by-step solution with:
            - Given values clearly stated
            - Formula/method used  
            - Each calculation step explained
            - Final answer clearly stated
            
            CRITICAL - DO NOT USE LaTeX! No dollar signs ($), no backslashes (\\), no LaTeX commands!
            
            USE ONLY these Unicode mathematical symbols directly:
            - √ (square root), ∛ (cube root)
            - ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁰ ⁺ ⁻ (superscripts)
            - ₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉ (subscripts)
            - × (multiplication), ÷ (division), ± (plus-minus)
            - π θ φ Φ ψ Ψ α β γ δ ε ω (Greek letters)
            - ∑ ∫ ∂ ∇ ∞ (calculus symbols)
            - ≠ ≤ ≥ ≈ ≡ (comparisons)
            - |ψ⟩ ⟨ψ| (quantum bra-ket notation with ⟨ and ⟩)
            - ½ ⅓ ¼ ⅔ ¾ (fractions)
            - ⊗ ⊕ (tensor product, direct sum)
            - → ← ↔ ⇒ ⇐ ⇔ (arrows)
            
            WRONG: $\\psi$, $\\sqrt{2}$, $x^2$, \\otimes, \\rangle
            CORRECT: ψ, √2, x², ⊗, ⟩
            
            Example: Write |ψ⟩ = (1/√2)(|0⟩ + |1⟩) NOT $|\\psi\\rangle = \\frac{1}{\\sqrt{2}}(|0\\rangle + |1\\rangle)$""",
        'MIXED': """Generate a mix of question types. For MCQ, include 4 options (A, B, C, D) in the question using \\n for newlines. For True/False, include A) True and B) False options."""
    }
    return prompts.get(question_type, prompts['SHORT'])

def generate_questions_with_gemini(text, difficulty, num_questions=5, question_type='SHORT'):
    """Generate questions using Gemini AI"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    type_instruction = get_question_type_prompt(question_type)
    
    prompt = f"""Based on the following text, generate {num_questions} {difficulty} level questions with answers.

QUESTION TYPE: {type_instruction}

CRITICAL FORMATTING RULES:
1. DO NOT USE LaTeX! No dollar signs ($), no backslashes (\\), no LaTeX commands!
2. Use ONLY Unicode symbols for math: √ ² ³ π θ φ ψ α β γ δ × ÷ ± ≠ ≤ ≥ ∑ ∫ |ψ⟩ ⟨ψ| ⊗ ⊕ → ⇒
3. WRONG: $\\psi$, $\\sqrt{{2}}$, \\alpha, \\beta, \\otimes
4. CORRECT: ψ, √2, α, β, ⊗
5. All questions and answers must be clear and understandable
6. Vary the complexity based on the difficulty level

Text:
{text[:8000]}

Return ONLY a JSON array with this structure, no markdown:
[
    {{"question": "...", "answer": "...", "marks": 1, "type": "{question_type}"}}
]"""
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        logger.info(f"Generated {num_questions} questions successfully")
        return json.loads(response_text)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error generating questions: {e}")
        return []

def extract_topics_with_gemini(text):
    """Use Gemini AI to extract meaningful topics with explanations and math problems from text"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""Analyze the following text and extract:
1. Main topics/subjects with explanations
2. Any mathematical problems, equations, or numerical examples with step-by-step solutions

Instructions:
1. Identify 5-15 key topics or concepts from the text
2. Each topic should be a clear, concise phrase (2-6 words)
3. Provide a brief explanation/answer (2-4 sentences) for each topic
4. If there are mathematical problems, formulas, or numerical examples in the text, include them with:
   - The problem statement
   - Step-by-step solution
   - Final answer
5. Use "type": "topic" for regular topics and "type": "math" for mathematical problems
6. For math problems, write equations in plain text (e.g., "2x + 5 = 15" not LaTeX)
7. Return ONLY a JSON array, no markdown

Text:
{text[:12000]}

Return format (JSON array of objects):
[
    {{"type": "topic", "topic": "Topic Name", "explanation": "Brief explanation..."}},
    {{"type": "math", "topic": "Problem Title", "problem": "The mathematical problem statement", "solution": "Step 1: ... Step 2: ... Final Answer: ..."}},
    {{"type": "topic", "topic": "Another Topic", "explanation": "Explanation..."}}
]"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        topics = json.loads(response_text)
        return topics if isinstance(topics, list) else []
    except Exception as e:
        logger.error(f"Error extracting topics with Gemini: {e}")
        return []

def pdf_topic_generator(request):
    if request.method == 'POST':
        try:
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                raise ValidationError('Please upload a PDF file.')

            ext = validate_file(pdf_file)
            if ext != '.pdf':
                raise ValidationError('Only PDF files are supported.')

            text = extract_text_from_pdf(pdf_file)
            if not text.strip():
                raise ValidationError('Could not extract text from the PDF.')

            # Use AI to extract topics
            topics = extract_topics_with_gemini(text)
            
            if not topics:
                raise ValidationError('Could not extract topics. Please try again.')
            
            # Store filename for display
            filename = pdf_file.name

            return render(request, 'pdf_topic_generator.html', {
                'topics': topics,
                'filename': filename,
                'success': True
            })

        except ValidationError as e:
            return render(request, 'pdf_topic_generator.html', {'error': str(e)})
        except Exception as e:
            logger.error(f"Error in topic generator: {e}", exc_info=True)
            return render(request, 'pdf_topic_generator.html', {'error': f'An unexpected error occurred: {str(e)}'})

    return render(request, 'pdf_topic_generator.html')

def index(request):
    """Home page"""
    return render(request, 'index.html')

def features(request):
    """Features overview page"""
    return render(request, 'features.html')

def upload(request):
    if request.method == 'POST':
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        
        try:
            study_file = request.FILES.get('study_file')
            difficulty = request.POST.get('difficulty', 'Medium')
            num_questions = request.POST.get('num_questions', 5)
            question_type = request.POST.get('question_type', 'SHORT')
            
            # Validate inputs
            ext = validate_file(study_file)
            num_questions = validate_num_questions(num_questions)
            difficulty = validate_difficulty(difficulty)
            question_type = validate_question_type(question_type)
            
            # Extract text
            text = extract_text(study_file, ext)
            
            if not text.strip():
                raise ValidationError('Could not extract text from file')
            
            # Generate questions
            questions_data = generate_questions_with_gemini(text, difficulty, num_questions, question_type)
            
            if not questions_data:
                raise ValidationError('Could not generate questions. Please try again.')
            
            # Save questions
            topic = os.path.splitext(study_file.name)[0]
            saved_questions = []
            
            for q_data in questions_data:
                # Ensure text fields are strings, not dicts
                q_text = q_data.get('question', '')
                q_answer = q_data.get('answer', '')
                
                # Handle case where answer might be a dict (e.g., with steps)
                if isinstance(q_text, dict):
                    q_text = str(q_text)
                if isinstance(q_answer, dict):
                    # If answer is structured, convert to string
                    q_answer = '\n'.join(f"{k}: {v}" for k, v in q_answer.items())
                
                question = Question.objects.create(
                    text=str(q_text),
                    topic=topic,
                    difficulty=difficulty,
                    question_type=q_data.get('type', question_type),
                    marks=q_data.get('marks', 1),
                    answer=str(q_answer)
                )
                saved_questions.append(question)
            
            logger.info(f"Saved {len(saved_questions)} questions for topic: {topic}")
            
            # Check which button was clicked
            include_answers = request.POST.get('include_answers', 'no') == 'yes'
            
            # Generate PDF
            pdf_buffer = generate_pdf_file(saved_questions, topic, include_answers=include_answers)
            
            suffix = "Questions_and_Answers" if include_answers else "Questions"
            filename = f"{topic}_{suffix}.pdf"
            
            if is_ajax:
                pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode('ascii')
                return JsonResponse({'filename': filename, 'pdf': pdf_b64})
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            if is_ajax:
                return JsonResponse({'error': str(e)}, status=400)
            return render(request, 'upload.html', {'error': str(e)})
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            if is_ajax:
                return JsonResponse({'error': f'Error: {str(e)}'}, status=500)
            return render(request, 'upload.html', {'error': f'Error: {str(e)}'})
    
    return render(request, 'upload.html')

def generate_short_notes_with_gemini(text):
    """Generate concise short notes using Gemini AI"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""Analyze the following text and generate comprehensive SHORT NOTES for study purposes.

INSTRUCTIONS:
1. Create well-organized, concise notes covering all important concepts
2. Use bullet points and numbered lists for clarity
3. Highlight key terms, definitions, formulas, and important facts
4. Group related concepts under clear headings/subheadings
5. Keep explanations brief but complete
6. Add memory tips or mnemonics where helpful

CRITICAL - DO NOT USE LaTeX! No dollar signs ($), no backslashes (\\), no LaTeX commands!

USE ONLY Unicode mathematical symbols directly:
- √ (square root), ∛ (cube root)
- ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁰ ⁺ ⁻ (superscripts for powers)
- ₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉ (subscripts)
- × ÷ ± (operators)
- π θ φ Φ ψ Ψ α β γ δ ε ω λ μ σ (Greek letters)
- ∑ ∫ ∂ ∇ ∞ (calculus)
- ≠ ≤ ≥ ≈ ≡ (comparisons)
- |ψ⟩ ⟨ψ| (quantum notation with ⟨ ⟩)
- ½ ⅓ ¼ ⅔ ¾ (fractions)
- ⊗ ⊕ → ⇒ ↔ (operators and arrows)

WRONG: $\\psi$, $\\sqrt{{2}}$, $x^2$, \\alpha, \\beta
CORRECT: ψ, √2, x², α, β

FORMAT YOUR RESPONSE AS:
- Use "##" for main headings
- Use "###" for subheadings  
- Use "•" for bullet points
- Use "→" for definitions or explanations
- Use "⚡" for key points to remember
- Use "📝" for formulas
- Use "💡" for tips/mnemonics

Text to analyze:
{text[:15000]}

Generate structured short notes:"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating short notes: {e}")
        return None

def short_notes(request):
    """Generate short notes from uploaded PDF"""
    if request.method == 'POST':
        try:
            study_file = request.FILES.get('study_file')
            
            # Validate file
            ext = validate_file(study_file)
            
            # Extract text
            text = extract_text(study_file, ext)
            
            if not text.strip():
                raise ValidationError('Could not extract text from file')
            
            # Generate short notes
            notes = generate_short_notes_with_gemini(text)
            
            if not notes:
                raise ValidationError('Could not generate notes. Please try again.')
            
            filename = os.path.splitext(study_file.name)[0]
            
            # Store notes in session for PDF download
            request.session['short_notes'] = notes
            request.session['short_notes_filename'] = filename
            
            return render(request, 'short_notes.html', {
                'notes': notes,
                'filename': filename,
                'success': True
            })
            
        except ValidationError as e:
            return render(request, 'short_notes.html', {'error': str(e)})
        except Exception as e:
            logger.error(f"Error generating short notes: {e}", exc_info=True)
            return render(request, 'short_notes.html', {'error': f'An error occurred: {str(e)}'})
    
    return render(request, 'short_notes.html')

def download_notes_pdf(request):
    """Download short notes as PDF"""
    notes = request.session.get('short_notes')
    filename = request.session.get('short_notes_filename', 'notes')
    
    if not notes:
        return HttpResponse('No notes available. Please generate notes first.', status=400)
    
    try:
        pdf_buffer = generate_notes_pdf(notes, filename)
        
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="short_notes_{filename}.pdf"'
        return response
        
    except Exception as e:
        logger.error(f"Error generating notes PDF: {e}", exc_info=True)
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)

def history(request):
    """View past generated questions"""
    questions = Question.objects.all()
    
    # Filter by topic
    topic = request.GET.get('topic')
    if topic:
        questions = questions.filter(topic__icontains=topic)
    
    # Filter by difficulty
    difficulty = request.GET.get('difficulty')
    if difficulty:
        questions = questions.filter(difficulty=difficulty)
    
    # Pagination
    paginator = Paginator(questions, 20)
    page = request.GET.get('page', 1)
    questions_page = paginator.get_page(page)
    
    # Get unique topics for filter dropdown
    topics = Question.objects.values_list('topic', flat=True).distinct()
    
    return render(request, 'history.html', {
        'questions': questions_page,
        'topics': topics,
        'current_topic': topic,
        'current_difficulty': difficulty
    })
