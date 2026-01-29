import os
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
import json
import base64
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from .utils import generate_pdf_file
from .models import Question

# 1. Setup Gemini
# Explicitly provide the path to the .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
	raise ValueError("GEMINI_API_KEY environment variable not set")

genai.configure(api_key=api_key)

def extract_text_from_pdf(pdf_file):
	"""Extract text from uploaded PDF file"""
	pdf_reader = PyPDF2.PdfReader(pdf_file)
	text = ""
	for page in pdf_reader.pages:
		text += page.extract_text()
	return text

def generate_questions_with_gemini(text, difficulty, num_questions=5):
	"""Generate questions using Gemini AI"""
	model = genai.GenerativeModel('gemini-2.5-flash')
	
	prompt = f"""Based on the following text, generate {num_questions} {difficulty} level questions with answers.

IMPORTANT FORMATTING RULES:
1. Generate a mix of:
	 - Theoretical questions (definition, concept, explanation type questions)
	 - Numerical/Mathematical problems (calculations, practical problems with simple numbers)
	 - Problem-solving questions

2. For mathematical problems:
	 - Use SIMPLE PLAIN TEXT format only (no complex symbols, no LaTeX, no special notation)
	 - Write math like: "2x + 5 = 15, solve for x" instead of using complex symbols
	 - Use words like "power of", "square root of", "multiply", "divide" instead of symbols
	 - Example: "If 2 times a number plus 5 equals 15, what is the number?"
	 - Make answers simple and clear: "The answer is 5"

3. Make sure approximately 50% are theoretical and 50% are mathematical/numerical problems.
4. All questions and answers must be CLEAR and EASILY UNDERSTANDABLE.

Text:
{text}

Please return ONLY a JSON array with this exact structure, no markdown, no code blocks, just pure JSON:
[
	{{"question": "...", "answer": "...", "marks": 1}},
	{{"question": "...", "answer": "...", "marks": 1}}
]

REMEMBER: Keep all questions and answers in plain, simple English with basic mathematical notation only."""
	
	try:
		response = model.generate_content(prompt)
		response_text = response.text.strip()
		
		# Remove markdown code blocks if present
		if response_text.startswith("```"):
			response_text = response_text.split("```")[1]
			if response_text.startswith("json"):
				response_text = response_text[4:]
			response_text = response_text.strip()
		
		print(f"DEBUG: Response from Gemini: {response_text}")
		
		# Parse the JSON response
		questions_data = json.loads(response_text)

		# Detect numeric/math questions by keywords or digits
		def is_numeric_q(q_text):
			q = q_text.lower()
			math_keywords = ['solve', 'calculate', 'find', 'evaluate', 'how many', 'what is', 'times', 'multiply', 'divide', 'sum', 'difference', 'product', 'percentage', 'percent', 'km', 'm', 'cm', 'kg', 'g', 'ms', 's', 'minutes', 'hours']
			if any(k in q for k in math_keywords):
				return True
			# presence of digits usually indicates numeric problem
			if any(ch.isdigit() for ch in q):
				return True
			return False

		numeric_count = sum(1 for q in questions_data if is_numeric_q(q.get('question','')))
		print(f"DEBUG: numeric_count={numeric_count} / requested {num_questions}")

		# If not enough numeric questions, request only numeric problems and merge
		if numeric_count < (num_questions // 2):
			need = max(1, (num_questions // 2) - numeric_count)
			print(f"DEBUG: Requesting {need} additional numeric problems from model")
			num_prompt = f"""From the same source text, generate {need} additional NUMERICAL/MATHEMATICAL problems (clear plain-text format) with answers.\n\nText:\n{text}\n\nReturn ONLY a JSON array of objects with keys 'question','answer','marks'."""
			try:
				num_resp = model.generate_content(num_prompt)
				num_text = num_resp.text.strip()
				if num_text.startswith('```'):
					num_text = num_text.split('```')[1]
					if num_text.startswith('json'):
						num_text = num_text[4:]
					num_text = num_text.strip()
				print(f"DEBUG: numeric response: {num_text}")
				additional = json.loads(num_text)
				# Append up to 'need' additional questions
				for item in additional[:need]:
					questions_data.append(item)
			except Exception as e:
				print(f"DEBUG: Failed to fetch additional numeric questions: {e}")

		# Trim or pad to requested num_questions
		if len(questions_data) > num_questions:
			questions_data = questions_data[:num_questions]
		elif len(questions_data) < num_questions:
			# If too few, keep as-is (could also request more) but log
			print(f"DEBUG: Only generated {len(questions_data)} questions, fewer than requested {num_questions}")

		return questions_data
	except json.JSONDecodeError as e:
		print(f"DEBUG: JSON Parse Error: {e}")
		print(f"DEBUG: Response was: {response_text if 'response_text' in locals() else 'No response'}")
		return []
	except Exception as e:
		print(f"DEBUG: Error in generate_questions_with_gemini: {e}")
		import traceback
		traceback.print_exc()
		return []

# View function for the index page
def index(request):
	if request.method == 'POST':
		# Check if this is an AJAX request early
		is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
		print(f"DEBUG: AJAX request: {is_ajax}")
		
		try:
			print("DEBUG: POST request received")
			
			# Get uploaded file, difficulty, and number of questions
			study_file = request.FILES.get('study_file')
			difficulty = request.POST.get('difficulty', 'Medium')
			num_questions = int(request.POST.get('num_questions', 5))
			
			print(f"DEBUG: File: {study_file}, Difficulty: {difficulty}, Questions: {num_questions}")
			
			if not study_file:
				print("ERROR: No file uploaded")
				if is_ajax:
					return JsonResponse({'error': 'Please upload a file'}, status=400)
				return render(request, 'index.html', {'error': 'Please upload a file'})
			
			# Extract text from PDF
			print("DEBUG: Extracting text from PDF...")
			text = extract_text_from_pdf(study_file)
			
			print(f"DEBUG: Extracted text length: {len(text)}")
			
			if not text.strip():
				print("ERROR: Could not extract text from PDF")
				if is_ajax:
					return JsonResponse({'error': 'Could not extract text from PDF'}, status=400)
				return render(request, 'index.html', {'error': 'Could not extract text from PDF'})
			
			# Generate questions with Gemini
			print("DEBUG: Generating questions with Gemini...")
			questions_data = generate_questions_with_gemini(text, difficulty, num_questions)
			
			print(f"DEBUG: Generated {len(questions_data)} questions")
			
			if not questions_data:
				print("ERROR: No questions generated")
				if is_ajax:
					return JsonResponse({'error': 'Could not generate questions. Please try again.'}, status=400)
				return render(request, 'index.html', {'error': 'Could not generate questions. Please try again.'})
			
			# Save questions to database
			topic = study_file.name.replace('.pdf', '')
			saved_questions = []
			
			print(f"DEBUG: Saving {len(questions_data)} questions to database...")
			
			for q_data in questions_data:
				question = Question.objects.create(
					text=q_data.get('question', ''),
					topic=topic,
					difficulty=difficulty,
					marks=q_data.get('marks', 1),
					answer=q_data.get('answer', '')
				)
				saved_questions.append(question)
			
			print("DEBUG: Questions saved. Generating PDF...")
			
			# Generate PDF with questions
			pdf_buffer = generate_pdf_file(saved_questions, topic)
			
			print("DEBUG: PDF generated. Returning response...")
			
# Return PDF as download or JSON (AJAX)
			# If request is AJAX (from client-side), return base64 PDF in JSON so client can preview and download
			is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
			if is_ajax:
				pdf_bytes = pdf_buffer.getvalue()
				pdf_b64 = base64.b64encode(pdf_bytes).decode('ascii')
				return JsonResponse({'filename': f'questions_{topic}.pdf', 'pdf': pdf_b64})
			
			response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
			response['Content-Disposition'] = f'attachment; filename="questions_{topic}.pdf"'
			return response
			
		except Exception as e:
			print(f"ERROR: {str(e)}")
			import traceback
			traceback.print_exc()
			if is_ajax:
				return JsonResponse({'error': f'Error: {str(e)}'}, status=500)
			return render(request, 'index.html', {'error': f'Error: {str(e)}'})
	
	return render(request, 'index.html')
