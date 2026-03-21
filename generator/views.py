import os
import uuid
import json
import re
from typing import Any
from io import BytesIO
from dotenv import load_dotenv
import google.generativeai as genai
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.db.models import QuerySet
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Question, QuizSession, FlashcardSet, Flashcard
from .utils import generate_pdf_file, generate_professional_pdf, generate_docx_file, extract_text_from_file


dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if not os.path.exists(dotenv_path):
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'QuestionGen', '.env')
load_dotenv(dotenv_path=dotenv_path)


def get_gemini_model() -> genai.GenerativeModel:
    api_key: str | None = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash')


def _clean_gemini_json(response_text: str) -> list[dict[str, Any]] | dict[str, Any]:
    text: str = response_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def _extract_text(request: HttpRequest) -> tuple[str, str]:
    study_file = request.FILES.get('study_file') or request.FILES.get('pdf_file')
    pasted_text: str = request.POST.get('pasted_text', '').strip()
    filename: str = 'Pasted Text'

    if study_file:
        text: str = extract_text_from_file(study_file)
        filename = study_file.name
    elif pasted_text:
        text = pasted_text
    else:
        text = ''

    return text, filename


def index(request: HttpRequest) -> HttpResponse:
    return render(request, 'index.html')


def features(request: HttpRequest) -> HttpResponse:
    return render(request, 'features.html')


def history(request: HttpRequest) -> HttpResponse:
    questions: QuerySet[Question] = Question.objects.all()
    return render(request, 'history.html', {'questions': questions})


def upload(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        is_ajax: bool = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        try:
            text, filename = _extract_text(request)
            difficulty: str = request.POST.get('difficulty', 'Medium')
            num_questions: int = int(request.POST.get('num_questions', 5))
            question_type: str = request.POST.get('question_type', 'SHORT')
            include_answers: bool = request.POST.get('include_answers', 'no') == 'yes'

            if not text.strip():
                raise ValueError('Please upload a file or paste text')

            from .generators import generate_questions_with_gemini
            questions_data = generate_questions_with_gemini(text, difficulty, num_questions, question_type)
            if not questions_data:
                raise ValueError('Could not generate questions. Please check your API key and try again.')

            topic: str = os.path.splitext(filename)[0] if '.' in filename else filename
            saved_questions: list[Question] = _save_questions(questions_data, topic, difficulty, question_type, share=True)

            question_ids: str = ','.join(str(q.id) for q in saved_questions)
            preview_url: str = f'/preview/?ids={question_ids}'

            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'redirect': preview_url})

            return redirect(preview_url)

        except ValueError as e:
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'error': str(e)}, status=400)
            return render(request, 'upload.html', {'error': str(e)})
        except Exception as e:
            import traceback
            error_detail = str(e)
            print(f"ERROR in upload view: {error_detail}")
            traceback.print_exc()
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'error': f'Server error: {error_detail}'}, status=500)
            return render(request, 'upload.html', {'error': f'Server error: {error_detail}'})

    return render(request, 'upload.html')


def _save_questions(
    questions_data: list[dict[str, Any]],
    topic: str,
    difficulty: str,
    question_type: str,
    share: bool = False
) -> list[Question]:
    share_id: str | None = str(uuid.uuid4()) if share else None
    saved: list[Question] = []
    for q_data in questions_data:
        q_text = q_data.get('question', '')
        q_answer = q_data.get('answer', '')
        if isinstance(q_text, dict):
            q_text = str(q_text)
        if isinstance(q_answer, dict):
            q_answer = '\n'.join(f"{k}: {v}" for k, v in q_answer.items())
        q = Question.objects.create(
            text=str(q_text),
            topic=topic,
            difficulty=difficulty,
            marks=q_data.get('marks', 1),
            answer=str(q_answer),
            explanation=q_data.get('explanation', ''),
            question_type=q_data.get('type', question_type.lower()),
            bloom_level=q_data.get('bloom', 'understand'),
            share_id=share_id if not saved else None,
        )
        saved.append(q)
    return saved


def preview_questions(request: HttpRequest) -> HttpResponse:
    ids_str: str = request.GET.get('ids', '')
    if not ids_str:
        return redirect('upload')
    ids: list[int] = [int(i) for i in ids_str.split(',') if i.isdigit()]
    questions: QuerySet[Question] = Question.objects.filter(id__in=ids)
    if not questions.exists():
        return redirect('upload')

    topic: str = questions.first().topic
    share_id: str | None = questions.first().share_id
    share_url: str = request.build_absolute_uri(f'/share/{share_id}/') if share_id else ''

    return render(request, 'preview.html', {
        'questions': questions,
        'topic': topic,
        'question_ids': ids_str,
        'share_url': share_url,
    })


def download_preview_pdf(request: HttpRequest) -> HttpResponse:
    ids_str: str = request.GET.get('ids', '')
    ids: list[int] = [int(i) for i in ids_str.split(',') if i.isdigit()]
    questions: list[Question] = list(Question.objects.filter(id__in=ids))
    if not questions:
        return HttpResponse('No questions found.', status=400)

    topic: str = questions[0].topic
    include_answers: bool = request.GET.get('answers', 'yes') == 'yes'
    institution: str = request.GET.get('institution', '')
    duration: str = request.GET.get('duration', '')

    pdf_buffer: BytesIO = generate_professional_pdf(questions, topic, include_answers, institution, duration)
    suffix: str = "with_answers" if include_answers else "questions_only"
    response: HttpResponse = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{topic}_{suffix}.pdf"'
    return response


def export_docx(request: HttpRequest) -> HttpResponse:
    ids_str: str = request.GET.get('ids', '')
    ids: list[int] = [int(i) for i in ids_str.split(',') if i.isdigit()]
    questions: list[Question] = list(Question.objects.filter(id__in=ids))
    if not questions:
        return HttpResponse('No questions found.', status=400)

    topic: str = questions[0].topic
    include_answers: bool = request.GET.get('answers', 'yes') == 'yes'
    docx_buffer: BytesIO = generate_docx_file(questions, topic, include_answers)

    response: HttpResponse = HttpResponse(
        docx_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{topic}_questions.docx"'
    return response


def share_paper(request: HttpRequest, share_id: str) -> HttpResponse:
    question: Question | None = Question.objects.filter(share_id=share_id).first()
    if not question:
        return render(request, 'preview.html', {'error': 'Shared paper not found.'})

    questions: QuerySet[Question] = Question.objects.filter(
        topic=question.topic,
        created_at__gte=question.created_at,
    ).filter(
        Q(share_id=share_id) | Q(id__gte=question.id)
    ).filter(topic=question.topic)[:50]

    return render(request, 'preview.html', {
        'questions': questions,
        'topic': question.topic,
        'question_ids': ','.join(str(q.id) for q in questions),
        'share_url': request.build_absolute_uri(),
        'shared_view': True,
    })


from django.db.models import Q


def regenerate_question(request: HttpRequest, question_id: int) -> HttpResponse:
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        question: Question = get_object_or_404(Question, id=question_id)
        model: genai.GenerativeModel = get_gemini_model()
        prompt: str = f"""Generate 1 {question.difficulty} level {question.get_question_type_display()} question about "{question.topic}".

Return ONLY a JSON object (not array):
{{"question": "...", "answer": "...", "explanation": "...", "marks": {question.marks}, "type": "{question.question_type}", "bloom": "understand"}}"""

        response = model.generate_content(prompt)
        data: dict[str, Any] = _clean_gemini_json(response.text)
        if isinstance(data, list):
            data = data[0]

        question.text = data.get('question', question.text)
        question.answer = data.get('answer', question.answer)
        question.explanation = data.get('explanation', question.explanation)
        question.bloom_level = data.get('bloom', question.bloom_level)
        question.save()

        from django.http import JsonResponse
        return JsonResponse({
            'id': question.id,
            'text': question.text,
            'answer': question.answer,
            'explanation': question.explanation,
            'question_type': question.question_type,
            'marks': question.marks,
            'bloom_level': question.bloom_level,
        })
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({'error': str(e)}, status=500)


def delete_question(request: HttpRequest, question_id: int) -> HttpResponse:
    if request.method != 'POST':
        from django.http import JsonResponse
        return JsonResponse({'error': 'POST required'}, status=405)
    from django.shortcuts import get_object_or_404
    question: Question = get_object_or_404(Question, id=question_id)
    question.delete()
    from django.http import JsonResponse
    return JsonResponse({'success': True})


def start_quiz(request: HttpRequest) -> HttpResponse:
    ids_str: str = request.GET.get('ids', '')
    if not ids_str:
        return redirect('upload')

    ids: list[int] = [int(i) for i in ids_str.split(',') if i.isdigit()]
    questions: list[Question] = list(Question.objects.filter(id__in=ids))
    if not questions:
        return redirect('upload')

    session: QuizSession = QuizSession.objects.create(
        topic=questions[0].topic,
        total=len(questions),
    )
    session.questions.set(questions)

    total_marks: int = sum(q.marks for q in questions)

    return render(request, 'quiz.html', {
        'quiz_session': session,
        'questions': questions,
        'total_marks': total_marks,
        'completed': False,
    })


def submit_quiz(request: HttpRequest, session_id: str) -> HttpResponse:
    session: QuizSession = QuizSession.objects.get(session_id=session_id)
    if request.method != 'POST':
        return redirect('index')

    questions: list[Question] = list(session.questions.all())
    session.time_taken = int(request.POST.get('time_taken', 0))

    score: int = 0
    answers: list[dict[str, Any]] = []
    for q in questions:
        user_answer: str = request.POST.get(f'answer_{q.id}', '').strip()
        correct_answer: str = (q.answer or '').strip()

        is_correct: bool = False
        if q.question_type in ('mcq', 'true_false'):
            if q.question_type == 'mcq':
                is_correct = bool(user_answer and correct_answer and user_answer[0].upper() == correct_answer[0].upper())
            else:
                is_correct = user_answer.lower() == correct_answer.lower()
        elif q.question_type == 'numerical':
            try:
                user_num: float = float(re.sub(r'[^\d.\-]', '', user_answer))
                correct_num: float = float(re.sub(r'[^\d.\-]', '', correct_answer))
                is_correct = abs(user_num - correct_num) < 0.01
            except (ValueError, TypeError):
                is_correct = user_answer.lower() == correct_answer.lower()
        else:
            user_words: set[str] = set(user_answer.lower().split())
            correct_words: set[str] = set(correct_answer.lower().split())
            if correct_words:
                overlap: float = len(user_words & correct_words) / len(correct_words)
                is_correct = overlap > 0.6

        if is_correct:
            score += q.marks

        answers.append({
            'question_text': q.text,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'explanation': q.explanation or '',
        })

    total_marks: int = sum(q.marks for q in questions)
    session.score = score
    session.completed = True
    session.save()

    percentage: int = round(score / total_marks * 100) if total_marks else 0

    return render(request, 'quiz.html', {
        'quiz_session': session,
        'questions': questions,
        'completed': True,
        'results': {
            'score': score,
            'total': total_marks,
            'percentage': percentage,
            'answers': answers,
        },
    })


def flashcards(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        try:
            text, filename = _extract_text(request)
            if not text.strip():
                return render(request, 'flashcards.html', {'error': 'Please upload a file or paste text'})

            model: genai.GenerativeModel = get_gemini_model()
            prompt: str = f"""Based on the following text, generate 10-20 flashcards for studying.
Each flashcard should have a "front" (question/term/concept) and "back" (answer/definition/explanation).
Cover all key concepts.

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"front": "What is ...?", "back": "It is ..."}}]"""

            response = model.generate_content(prompt)
            cards_data: list[dict[str, str]] = _clean_gemini_json(response.text)

            topic: str = os.path.splitext(filename)[0] if '.' in filename else filename
            fc_set: FlashcardSet = FlashcardSet.objects.create(topic=topic)
            cards: list[dict[str, str]] = []
            for i, c in enumerate(cards_data):
                card: Flashcard = Flashcard.objects.create(
                    flashcard_set=fc_set,
                    front=c.get('front', ''),
                    back=c.get('back', ''),
                    order=i,
                )
                cards.append({'front': card.front, 'back': card.back})

            return render(request, 'flashcards.html', {
                'cards': cards,
                'topic': topic,
            })
        except Exception as e:
            return render(request, 'flashcards.html', {'error': str(e)})

    return render(request, 'flashcards.html')


def evaluate_answer(request: HttpRequest, question_id: int) -> HttpResponse:
    question: Question = Question.objects.get(id=question_id)

    if request.method == 'POST':
        student_answer: str = request.POST.get('student_answer', '').strip()
        if not student_answer:
            return render(request, 'evaluator.html', {
                'question': question,
                'error': 'Please type your answer before evaluating.',
            })

        try:
            model: genai.GenerativeModel = get_gemini_model()
            prompt: str = f"""You are an expert teacher evaluating a student's answer.

Question: {question.text}
Model Answer: {question.answer}
Student's Answer: {student_answer}
Maximum Marks: {question.marks}

Evaluate the student's answer and return ONLY a JSON object (no markdown, no code blocks):
{{
    "score": <number out of {question.marks}>,
    "total": {question.marks},
    "strengths": "What the student got right...",
    "weaknesses": "What was missed or incorrect...",
    "suggestions": "How to improve...",
    "model_answer": "{question.answer}"
}}

Be fair but thorough. Give partial marks where appropriate."""

            response = model.generate_content(prompt)
            evaluation: dict[str, Any] = _clean_gemini_json(response.text)
            evaluation['model_answer'] = question.answer

            return render(request, 'evaluator.html', {
                'question': question,
                'evaluation': evaluation,
                'student_answer': student_answer,
            })
        except Exception as e:
            return render(request, 'evaluator.html', {
                'question': question,
                'error': str(e),
                'student_answer': student_answer,
            })

    return render(request, 'evaluator.html', {'question': question})


@login_required
def analytics(request: HttpRequest) -> HttpResponse:
    from django.db.models import Count, Avg

    total_questions: int = Question.objects.count()
    total_topics: int = Question.objects.values('topic').distinct().count()
    total_quizzes: int = QuizSession.objects.filter(completed=True).count()
    avg_score_data: dict[str, float | None] = QuizSession.objects.filter(completed=True).aggregate(
        avg_score=Avg('score'),
        avg_total=Avg('total'),
    )
    if avg_score_data['avg_score'] and avg_score_data['avg_total']:
        avg_score: int = round(avg_score_data['avg_score'] / avg_score_data['avg_total'] * 100)
    else:
        avg_score = 0

    diff_qs: list[dict[str, Any]] = list(Question.objects.values('difficulty').annotate(count=Count('id')))
    difficulty_data: dict[str, int] = {d['difficulty']: d['count'] for d in diff_qs}

    type_qs: list[dict[str, Any]] = list(Question.objects.values('question_type').annotate(count=Count('id')))
    type_data: dict[str, int] = {t['question_type']: t['count'] for t in type_qs}

    bloom_qs: list[dict[str, Any]] = list(Question.objects.values('bloom_level').annotate(count=Count('id')))
    bloom_data: dict[str, int] = {b['bloom_level']: b['count'] for b in bloom_qs}

    recent: list[dict[str, Any]] = list(Question.objects.values('topic').annotate(
        count=Count('id'),
    ).order_by('-id')[:10])
    recent_activity: list[dict[str, str | int]] = []
    for r in recent:
        latest: Question | None = Question.objects.filter(topic=r['topic']).order_by('-created_at').first()
        recent_activity.append({
            'topic': r['topic'],
            'count': r['count'],
            'date': latest.created_at.strftime('%b %d, %Y') if latest else '',
        })

    return render(request, 'analytics.html', {
        'total_questions': total_questions,
        'total_topics': total_topics,
        'total_quizzes': total_quizzes,
        'avg_score': avg_score,
        'difficulty_data': json.dumps(difficulty_data),
        'type_data': json.dumps(type_data),
        'bloom_data': json.dumps(bloom_data),
        'recent_activity': recent_activity,
    })


def short_notes(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        try:
            text, filename = _extract_text(request)
            if not text.strip():
                return render(request, 'short_notes.html', {'error': 'Please upload a file'})

            notes: str | None = generate_short_notes_with_gemini(text)
            if not notes:
                return render(request, 'short_notes.html', {'error': 'Could not generate notes. Please try again.'})

            request.session['short_notes'] = notes
            request.session['short_notes_filename'] = filename

            return render(request, 'short_notes.html', {
                'success': True,
                'notes': notes,
                'filename': filename,
            })
        except Exception as e:
            return render(request, 'short_notes.html', {'error': str(e)})

    return render(request, 'short_notes.html')


def generate_short_notes_with_gemini(text: str) -> str | None:
    model: genai.GenerativeModel = get_gemini_model()
    prompt: str = f"""Generate concise short notes for studying from this text.
Organize by topic with ## headings and ### subheadings. Use bullet points.

Text:
{text}"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"DEBUG: Error generating notes: {e}")
        return None


def pdf_topic_generator(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        try:
            text, filename = _extract_text(request)
            if not text.strip():
                return render(request, 'pdf_topic_generator.html', {'error': 'Please upload a PDF file'})

            topics: list[dict[str, str]] = extract_topics_with_gemini(text)
            if not topics:
                return render(request, 'pdf_topic_generator.html', {'error': 'Could not extract topics. Please try again.'})

            request.session['extracted_topics'] = topics
            request.session['extracted_topics_filename'] = filename

            return render(request, 'pdf_topic_generator.html', {
                'success': True,
                'topics': topics,
                'filename': filename,
            })
        except Exception as e:
            return render(request, 'pdf_topic_generator.html', {'error': str(e)})

    return render(request, 'pdf_topic_generator.html')


def extract_topics_with_gemini(text: str) -> list[dict[str, str]]:
    model: genai.GenerativeModel = get_gemini_model()
    prompt: str = f"""Analyze the following text and extract the key topics/concepts.
For each, provide a brief explanation.

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"topic": "Topic Name", "explanation": "Brief explanation"}}]

Extract 5 to 15 topics."""

    try:
        response = model.generate_content(prompt)
        return _clean_gemini_json(response.text)
    except Exception as e:
        print(f"DEBUG: Error extracting topics: {e}")
        return []


def download_topics_pdf(request: HttpRequest) -> HttpResponse:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor

    topics: list[dict[str, str]] | None = request.session.get('extracted_topics')
    filename: str = request.session.get('extracted_topics_filename', 'topics')
    if not topics:
        return HttpResponse('No topics available. Please extract topics first.', status=400)

    buffer: BytesIO = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TopicTitle', parent=styles['Title'], fontSize=18, spaceAfter=20)
    heading_style = ParagraphStyle('TopicHeading', parent=styles['Heading2'], fontSize=13, spaceAfter=4, textColor=HexColor('#1a3a4a'))
    body_style = ParagraphStyle('TopicBody', parent=styles['Normal'], fontSize=11, spaceAfter=12, leading=16)

    story: list = []
    topic_label: str = os.path.splitext(filename)[0] if '.' in filename else filename
    story.append(Paragraph(f'Topics Extracted from: {topic_label}', title_style))
    story.append(Spacer(1, 12))

    for i, item in enumerate(topics, 1):
        topic_name: str = str(item.get('topic', '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        explanation: str = str(item.get('explanation', '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(f'{i}. {topic_name}', heading_style))
        story.append(Paragraph(explanation, body_style))

    doc.build(story)
    buffer.seek(0)

    safe_name: str = os.path.splitext(filename)[0]
    response: HttpResponse = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}_topics.pdf"'
    return response


def download_notes_pdf(request: HttpRequest) -> HttpResponse:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    notes: str | None = request.session.get('short_notes')
    filename: str = request.session.get('short_notes_filename', 'notes')
    if not notes:
        return HttpResponse('No notes available. Please generate notes first.', status=400)

    buffer: BytesIO = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle('NotesHeading', parent=styles['Heading2'], spaceAfter=6)
    body_style = ParagraphStyle('NotesBody', parent=styles['Normal'], spaceAfter=4, leading=14)

    story: list = []
    for line in notes.split('\n'):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], heading_style))
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], ParagraphStyle('Sub', parent=styles['Heading3'], spaceAfter=4)))
        else:
            clean: str = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if clean.startswith('- ') or clean.startswith('* '):
                clean = '&bull; ' + clean[2:]
            story.append(Paragraph(clean, body_style))

    doc.build(story)
    buffer.seek(0)

    topic: str = os.path.splitext(filename)[0]
    response: HttpResponse = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{topic}_short_notes.pdf"'
    return response


def signup_view(request: HttpRequest) -> HttpResponse:
    from django.contrib.auth import login
    from django.contrib.auth.forms import UserCreationForm

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})


def login_view(request: HttpRequest) -> HttpResponse:
    from django.contrib.auth import login as auth_login
    from django.contrib.auth.forms import AuthenticationForm

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request: HttpRequest) -> HttpResponse:
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return redirect('index')
