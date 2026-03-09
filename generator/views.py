import os
import uuid
import zipfile
from io import BytesIO
from dotenv import load_dotenv
import google.generativeai as genai
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Avg, Q
from django.contrib.auth import login, authenticate, logout as auth_logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .utils import generate_pdf_file, generate_professional_pdf, generate_docx_file, extract_text_from_file
from .models import Question, QuizSession, FlashcardSet, Flashcard

# Setup Gemini
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if not os.path.exists(dotenv_path):
	dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'QuestionGen', '.env')
load_dotenv(dotenv_path=dotenv_path)


def get_gemini_model():
	api_key = os.environ.get('GEMINI_API_KEY')
	if not api_key:
		raise ValueError("GEMINI_API_KEY environment variable not set")
	genai.configure(api_key=api_key)
	return genai.GenerativeModel('gemini-2.5-flash')


def _clean_gemini_json(response_text):
	"""Strip markdown fences from Gemini response and parse JSON."""
	text = response_text.strip()
	if text.startswith("```"):
		text = text.split("```")[1]
		if text.startswith("json"):
			text = text[4:]
		text = text.strip()
	return json.loads(text)


def _extract_text(request):
	"""Extract text from uploaded file or pasted text."""
	study_file = request.FILES.get('study_file') or request.FILES.get('pdf_file')
	pasted_text = request.POST.get('pasted_text', '').strip()
	filename = 'Pasted Text'

	if study_file:
		text = extract_text_from_file(study_file)
		filename = study_file.name
	elif pasted_text:
		text = pasted_text
	else:
		text = ''

	return text, filename


# ─── Question Generation ────────────────────────────────────────────

def generate_questions_with_gemini(text, difficulty, num_questions=5, question_type="MIXED"):
	model = get_gemini_model()
	qtype = question_type.upper()

	bloom_instruction = """
Also, for EACH question, assign a Bloom's Taxonomy level from: remember, understand, apply, analyze, evaluate, create.
Include it as a "bloom" field in the JSON."""

	if qtype == "SHORT":
		prompt = f"""Based on the following text, generate {num_questions} {difficulty} level SHORT ANSWER questions.
Each question should require a brief answer (1-3 sentences). Focus on key facts, definitions, and concepts.
{bloom_instruction}

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"question": "...", "answer": "...", "explanation": "", "marks": 2, "type": "short", "bloom": "understand"}}]"""

	elif qtype == "MCQ":
		prompt = f"""Based on the following text, generate {num_questions} {difficulty} level MULTIPLE CHOICE questions.

CRITICAL FORMATTING RULES:
1. The "question" field MUST contain the question stem FOLLOWED BY all 4 options on separate lines.
2. Options MUST be labeled A), B), C), D) each on its own line within the question string.
3. Use \\n to separate lines in the JSON string.
4. The "answer" field should state the correct option letter and its full text.

{bloom_instruction}

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"question": "What is quantum entanglement?\\nA) A classical physics phenomenon\\nB) The correlation between quantum states\\nC) A type of chemical bond\\nD) An electromagnetic wave", "answer": "B) The correlation between quantum states", "explanation": "Why B is correct", "marks": 1, "type": "mcq", "bloom": "remember"}}]

IMPORTANT: Every question MUST have exactly 4 options (A, B, C, D) embedded in the question field using \\n separators."""

	elif qtype == "TF":
		prompt = f"""Based on the following text, generate {num_questions} {difficulty} level TRUE or FALSE questions.
The "answer" field must be exactly "True" or "False". Mix true and false answers equally.
{bloom_instruction}

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"question": "Statement.", "answer": "True", "explanation": "Because ...", "marks": 1, "type": "true_false", "bloom": "remember"}}]"""

	elif qtype == "LONG":
		prompt = f"""Based on the following text, generate {num_questions} {difficulty} level LONG ANSWER questions.
Questions should require detailed, multi-paragraph answers.
{bloom_instruction}

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"question": "...", "answer": "Detailed answer...", "explanation": "", "marks": 5, "type": "long", "bloom": "analyze"}}]"""

	elif qtype == "NUMERICAL":
		prompt = f"""Based on the following text, generate {num_questions} {difficulty} level NUMERICAL/MATHEMATICAL problems.
Use plain text math (x^2, sqrt(x), *, /). Include step-by-step solution in "explanation".
{bloom_instruction}

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"question": "...", "answer": "Final answer", "explanation": "Step 1: ... Final Answer: ...", "marks": 3, "type": "numerical", "bloom": "apply"}}]"""

	else:
		prompt = f"""Based on the following text, generate {num_questions} {difficulty} level questions with a MIX of types.
Include Short Answer, MCQ (4 options A-D), True/False, and Numerical. Set "type" to: short, mcq, true_false, numerical, or long.
For MCQ questions: The "question" field MUST include the stem AND all 4 options (A), B), C), D)) separated by \\n.
{bloom_instruction}

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"question": "What is X?\\nA) Option1\\nB) Option2\\nC) Option3\\nD) Option4", "answer": "A) Option1", "explanation": "", "marks": 1, "type": "mcq", "bloom": "remember"}},
{{"question": "Define Y.", "answer": "Y is...", "explanation": "", "marks": 2, "type": "short", "bloom": "understand"}}]"""

	try:
		response = model.generate_content(prompt)
		return _clean_gemini_json(response.text)
	except Exception as e:
		print(f"DEBUG: Error generating questions: {e}")
		return []


def _save_questions(questions_data, topic, difficulty, question_type, share=False):
	"""Save question data list to DB and return saved Question objects."""
	share_id = str(uuid.uuid4()) if share else None
	saved = []
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


# ─── Page Views ──────────────────────────────────────────────────────

def index(request):
	return render(request, 'index.html')


def features(request):
	return render(request, 'features.html')


def history(request):
	questions = Question.objects.all()
	return render(request, 'history.html', {'questions': questions})


def upload(request):
	if request.method == 'POST':
		is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
		try:
			text, filename = _extract_text(request)
			difficulty = request.POST.get('difficulty', 'Medium')
			num_questions = int(request.POST.get('num_questions', 5))
			question_type = request.POST.get('question_type', 'SHORT')
			include_answers = request.POST.get('include_answers', 'no') == 'yes'

			if not text.strip():
				raise ValueError('Please upload a file or paste text')

			questions_data = generate_questions_with_gemini(text, difficulty, num_questions, question_type)
			if not questions_data:
				raise ValueError('Could not generate questions. Please try again.')

			topic = os.path.splitext(filename)[0] if '.' in filename else filename
			saved_questions = _save_questions(questions_data, topic, difficulty, question_type, share=True)

			question_ids = ','.join(str(q.id) for q in saved_questions)
			preview_url = f'/preview/?ids={question_ids}'

			if is_ajax:
				return JsonResponse({'redirect': preview_url})

			return redirect(preview_url)

		except Exception as e:
			if is_ajax:
				return JsonResponse({'error': str(e)}, status=400)
			return render(request, 'upload.html', {'error': str(e)})

	return render(request, 'upload.html')


# ─── Preview & Download ─────────────────────────────────────────────

def preview_questions(request):
	ids_str = request.GET.get('ids', '')
	if not ids_str:
		return redirect('upload')
	ids = [int(i) for i in ids_str.split(',') if i.isdigit()]
	questions = Question.objects.filter(id__in=ids)
	if not questions.exists():
		return redirect('upload')

	topic = questions.first().topic
	share_id = questions.first().share_id
	share_url = request.build_absolute_uri(f'/share/{share_id}/') if share_id else ''

	return render(request, 'preview.html', {
		'questions': questions,
		'topic': topic,
		'question_ids': ids_str,
		'share_url': share_url,
	})


def download_preview_pdf(request):
	ids_str = request.GET.get('ids', '')
	ids = [int(i) for i in ids_str.split(',') if i.isdigit()]
	questions = list(Question.objects.filter(id__in=ids))
	if not questions:
		return HttpResponse('No questions found.', status=400)

	topic = questions[0].topic
	include_answers = request.GET.get('answers', 'yes') == 'yes'
	institution = request.GET.get('institution', '')
	duration = request.GET.get('duration', '')

	pdf_buffer = generate_professional_pdf(questions, topic, include_answers, institution, duration)
	suffix = "with_answers" if include_answers else "questions_only"
	response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
	response['Content-Disposition'] = f'attachment; filename="{topic}_{suffix}.pdf"'
	return response


def export_docx(request):
	ids_str = request.GET.get('ids', '')
	ids = [int(i) for i in ids_str.split(',') if i.isdigit()]
	questions = list(Question.objects.filter(id__in=ids))
	if not questions:
		return HttpResponse('No questions found.', status=400)

	topic = questions[0].topic
	include_answers = request.GET.get('answers', 'yes') == 'yes'
	docx_buffer = generate_docx_file(questions, topic, include_answers)

	response = HttpResponse(
		docx_buffer.getvalue(),
		content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
	)
	response['Content-Disposition'] = f'attachment; filename="{topic}_questions.docx"'
	return response


def share_paper(request, share_id):
	question = Question.objects.filter(share_id=share_id).first()
	if not question:
		return render(request, 'preview.html', {'error': 'Shared paper not found.'})

	# Get all questions with the same topic created at the same time
	questions = Question.objects.filter(
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


# ─── Regenerate Single Question ─────────────────────────────────────

def regenerate_question(request, question_id):
	if request.method != 'POST':
		return JsonResponse({'error': 'POST required'}, status=405)

	question = get_object_or_404(Question, id=question_id)

	try:
		model = get_gemini_model()
		prompt = f"""Generate 1 {question.difficulty} level {question.get_question_type_display()} question about "{question.topic}".

Return ONLY a JSON object (not array):
{{"question": "...", "answer": "...", "explanation": "...", "marks": {question.marks}, "type": "{question.question_type}", "bloom": "understand"}}"""

		response = model.generate_content(prompt)
		data = _clean_gemini_json(response.text)
		if isinstance(data, list):
			data = data[0]

		question.text = data.get('question', question.text)
		question.answer = data.get('answer', question.answer)
		question.explanation = data.get('explanation', question.explanation)
		question.bloom_level = data.get('bloom', question.bloom_level)
		question.save()

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
		return JsonResponse({'error': str(e)}, status=500)


# ─── Delete Question ────────────────────────────────────────────────

def delete_question(request, question_id):
	if request.method != 'POST':
		return JsonResponse({'error': 'POST required'}, status=405)
	question = get_object_or_404(Question, id=question_id)
	question.delete()
	return JsonResponse({'success': True})


# ─── Quiz Mode ──────────────────────────────────────────────────────

def start_quiz(request):
	ids_str = request.GET.get('ids', '')
	if not ids_str:
		return redirect('upload')

	ids = [int(i) for i in ids_str.split(',') if i.isdigit()]
	questions = list(Question.objects.filter(id__in=ids))
	if not questions:
		return redirect('upload')

	session = QuizSession.objects.create(
		topic=questions[0].topic,
		total=len(questions),
	)
	session.questions.set(questions)

	total_marks = sum(q.marks for q in questions)

	return render(request, 'quiz.html', {
		'quiz_session': session,
		'questions': questions,
		'total_marks': total_marks,
		'completed': False,
	})


def submit_quiz(request, session_id):
	session = get_object_or_404(QuizSession, session_id=session_id)
	if request.method != 'POST':
		return redirect('index')

	questions = list(session.questions.all())
	session.time_taken = int(request.POST.get('time_taken', 0))

	score = 0
	answers = []
	for q in questions:
		user_answer = request.POST.get(f'answer_{q.id}', '').strip()
		correct_answer = (q.answer or '').strip()

		# Auto-grade MCQ and True/False
		is_correct = False
		if q.question_type in ('mcq', 'true_false'):
			# Compare first letter for MCQ, full match for TF
			if q.question_type == 'mcq':
				is_correct = user_answer and correct_answer and user_answer[0].upper() == correct_answer[0].upper()
			else:
				is_correct = user_answer.lower() == correct_answer.lower()
		elif q.question_type == 'numerical':
			# Try numeric comparison
			try:
				import re
				user_num = float(re.sub(r'[^\d.\-]', '', user_answer))
				correct_num = float(re.sub(r'[^\d.\-]', '', correct_answer))
				is_correct = abs(user_num - correct_num) < 0.01
			except (ValueError, TypeError):
				is_correct = user_answer.lower() == correct_answer.lower()
		else:
			# For short/long answers, mark as correct if >60% words match
			user_words = set(user_answer.lower().split())
			correct_words = set(correct_answer.lower().split())
			if correct_words:
				overlap = len(user_words & correct_words) / len(correct_words)
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

	total_marks = sum(q.marks for q in questions)
	session.score = score
	session.completed = True
	session.save()

	percentage = round(score / total_marks * 100) if total_marks else 0

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


# ─── Flashcards ─────────────────────────────────────────────────────

def flashcards(request):
	if request.method == 'POST':
		try:
			text, filename = _extract_text(request)
			if not text.strip():
				return render(request, 'flashcards.html', {'error': 'Please upload a file or paste text'})

			model = get_gemini_model()
			prompt = f"""Based on the following text, generate 10-20 flashcards for studying.
Each flashcard should have a "front" (question/term/concept) and "back" (answer/definition/explanation).
Cover all key concepts.

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"front": "What is ...?", "back": "It is ..."}}]"""

			response = model.generate_content(prompt)
			cards_data = _clean_gemini_json(response.text)

			topic = os.path.splitext(filename)[0] if '.' in filename else filename
			fc_set = FlashcardSet.objects.create(topic=topic)
			cards = []
			for i, c in enumerate(cards_data):
				card = Flashcard.objects.create(
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


# ─── AI Answer Evaluator ────────────────────────────────────────────

def evaluate_answer(request, question_id):
	question = get_object_or_404(Question, id=question_id)

	if request.method == 'POST':
		student_answer = request.POST.get('student_answer', '').strip()
		if not student_answer:
			return render(request, 'evaluator.html', {
				'question': question,
				'error': 'Please type your answer before evaluating.',
			})

		try:
			model = get_gemini_model()
			prompt = f"""You are an expert teacher evaluating a student's answer.

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
			evaluation = _clean_gemini_json(response.text)
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


# ─── Analytics Dashboard ────────────────────────────────────────────

def analytics(request):
	total_questions = Question.objects.count()
	total_topics = Question.objects.values('topic').distinct().count()
	total_quizzes = QuizSession.objects.filter(completed=True).count()
	avg_score_data = QuizSession.objects.filter(completed=True).aggregate(
		avg_score=Avg('score'),
		avg_total=Avg('total'),
	)
	if avg_score_data['avg_score'] and avg_score_data['avg_total']:
		avg_score = round(avg_score_data['avg_score'] / avg_score_data['avg_total'] * 100)
	else:
		avg_score = 0

	# Difficulty distribution
	diff_qs = Question.objects.values('difficulty').annotate(count=Count('id'))
	difficulty_data = {d['difficulty']: d['count'] for d in diff_qs}

	# Question type distribution
	type_qs = Question.objects.values('question_type').annotate(count=Count('id'))
	type_data = {t['question_type']: t['count'] for t in type_qs}

	# Bloom's taxonomy distribution
	bloom_qs = Question.objects.values('bloom_level').annotate(count=Count('id'))
	bloom_data = {b['bloom_level']: b['count'] for b in bloom_qs}

	# Recent activity
	recent = Question.objects.values('topic').annotate(
		count=Count('id'),
	).order_by('-id')[:10]
	recent_activity = []
	for r in recent:
		latest = Question.objects.filter(topic=r['topic']).order_by('-created_at').first()
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


# ─── Topic Extraction & Short Notes (existing) ──────────────────────

def extract_topics_with_gemini(text):
	model = get_gemini_model()
	prompt = f"""Analyze the following text and extract the key topics/concepts.
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


def generate_short_notes_with_gemini(text):
	model = get_gemini_model()
	prompt = f"""Generate concise short notes for studying from this text.
Organize by topic with ## headings and ### subheadings. Use bullet points.

Text:
{text}"""

	try:
		response = model.generate_content(prompt)
		return response.text.strip()
	except Exception as e:
		print(f"DEBUG: Error generating notes: {e}")
		return None


def pdf_topic_generator(request):
	if request.method == 'POST':
		try:
			text, filename = _extract_text(request)
			if not text.strip():
				return render(request, 'pdf_topic_generator.html', {'error': 'Please upload a PDF file'})

			topics = extract_topics_with_gemini(text)
			if not topics:
				return render(request, 'pdf_topic_generator.html', {'error': 'Could not extract topics. Please try again.'})

			return render(request, 'pdf_topic_generator.html', {
				'success': True,
				'topics': topics,
				'filename': filename,
			})
		except Exception as e:
			return render(request, 'pdf_topic_generator.html', {'error': str(e)})

	return render(request, 'pdf_topic_generator.html')


def short_notes(request):
	if request.method == 'POST':
		try:
			text, filename = _extract_text(request)
			if not text.strip():
				return render(request, 'short_notes.html', {'error': 'Please upload a file'})

			notes = generate_short_notes_with_gemini(text)
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


def download_notes_pdf(request):
	notes = request.session.get('short_notes')
	filename = request.session.get('short_notes_filename', 'notes')
	if not notes:
		return HttpResponse('No notes available. Please generate notes first.', status=400)

	from reportlab.lib.pagesizes import A4
	from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
	from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
	from reportlab.lib.units import inch

	buffer = BytesIO()
	doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
	styles = getSampleStyleSheet()
	heading_style = ParagraphStyle('NotesHeading', parent=styles['Heading2'], spaceAfter=6)
	body_style = ParagraphStyle('NotesBody', parent=styles['Normal'], spaceAfter=4, leading=14)

	story = []
	for line in notes.split('\n'):
		line = line.strip()
		if not line:
			story.append(Spacer(1, 6))
		elif line.startswith('## '):
			story.append(Paragraph(line[3:], heading_style))
		elif line.startswith('### '):
			story.append(Paragraph(line[4:], ParagraphStyle('Sub', parent=styles['Heading3'], spaceAfter=4)))
		else:
			clean = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
			if clean.startswith('- ') or clean.startswith('* '):
				clean = '&bull; ' + clean[2:]
			story.append(Paragraph(clean, body_style))

	doc.build(story)
	buffer.seek(0)

	topic = os.path.splitext(filename)[0]
	response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
	response['Content-Disposition'] = f'attachment; filename="{topic}_short_notes.pdf"'
	return response


# ─── Authentication ──────────────────────────────────────────────────

def signup_view(request):
	if request.method == 'POST':
		form = UserCreationForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			return redirect('index')
	else:
		form = UserCreationForm()
	return render(request, 'signup.html', {'form': form})


def login_view(request):
	if request.method == 'POST':
		form = AuthenticationForm(request, data=request.POST)
		if form.is_valid():
			user = form.get_user()
			login(request, user)
			return redirect('index')
	else:
		form = AuthenticationForm()
	return render(request, 'login.html', {'form': form})


def logout_view(request):
	auth_logout(request)
	return redirect('index')
