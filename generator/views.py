import os
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
import json
from django.http import FileResponse, HttpResponse
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
		try:
			print("DEBUG: POST request received")
			
			# Get uploaded file, difficulty, and number of questions
			study_file = request.FILES.get('study_file')
			difficulty = request.POST.get('difficulty', 'Medium')
			num_questions = int(request.POST.get('num_questions', 5))
			
			print(f"DEBUG: File: {study_file}, Difficulty: {difficulty}, Questions: {num_questions}")
			
			if not study_file:
				print("ERROR: No file uploaded")
				return render(request, 'index.html', {'error': 'Please upload a file'})
			
			# Extract text from PDF
			print("DEBUG: Extracting text from PDF...")
			text = extract_text_from_pdf(study_file)
			
			print(f"DEBUG: Extracted text length: {len(text)}")
			
			if not text.strip():
				print("ERROR: Could not extract text from PDF")
				return render(request, 'index.html', {'error': 'Could not extract text from PDF'})
			
			# Generate questions with Gemini
			print("DEBUG: Generating questions with Gemini...")
			questions_data = generate_questions_with_gemini(text, difficulty, num_questions)
			
			print(f"DEBUG: Generated {len(questions_data)} questions")
			
			if not questions_data:
				print("ERROR: No questions generated")
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
			
			# Return PDF as download
			response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
			response['Content-Disposition'] = f'attachment; filename="questions_{topic}.pdf"'
			return response
			
		except Exception as e:
			print(f"ERROR: {str(e)}")
			import traceback
			traceback.print_exc()
			return render(request, 'index.html', {'error': f'Error: {str(e)}'})
	
	return render(request, 'index.html')
