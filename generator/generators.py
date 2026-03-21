from typing import Any
import hashlib
import json
from functools import wraps
from io import BytesIO

try:
    import google.genai as genai_client
    USE_NEW_API = True
except ImportError:
    import google.generativeai as genai_client
    USE_NEW_API = False

from django.core.cache import cache


def cache_response(timeout: int = 300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key_parts = [func.__name__]
            for arg in args:
                if isinstance(arg, str):
                    cache_key_parts.append(arg[:100])
            for k, v in sorted(kwargs.items()):
                cache_key_parts.append(f"{k}:{str(v)[:50]}")
            cache_key = f"gemini:{hashlib.md5('|'.join(cache_key_parts).encode()).hexdigest()}"
            
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def get_gemini_model() -> Any:
    import os
    from dotenv import load_dotenv
    from django.conf import settings
    
    dotenv_path = settings.BASE_DIR / '.env'
    if not os.path.exists(dotenv_path):
        dotenv_path = settings.BASE_DIR / 'QuestionGen' / '.env'
    load_dotenv(dotenv_path=dotenv_path)
    
    api_key: str | None = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    if USE_NEW_API:
        client = genai_client.Client(api_key=api_key)
        return client
    else:
        genai_client.configure(api_key=api_key)
        return genai_client.GenerativeModel('gemini-2.5-flash')


def generate_content_with_gemini(model: Any, prompt: str) -> Any:
    if USE_NEW_API:
        response = model.models.generate_content(
            model="gemini-2.0-flash",
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        return response.text
    else:
        response = model.generate_content(prompt)
        return response.text


def _clean_gemini_json(response_text: str) -> list[dict[str, Any]] | dict[str, Any]:
    text: str = response_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


@cache_response(timeout=300)
def generate_questions_with_gemini(
    text: str,
    difficulty: str,
    num_questions: int = 5,
    question_type: str = "MIXED"
) -> list[dict[str, Any]]:
    model: Any = get_gemini_model()
    qtype: str = question_type.upper()

    bloom_instruction: str = """
Also, for EACH question, assign a Bloom's Taxonomy level from: remember, understand, apply, analyze, evaluate, create.
Include it as a "bloom" field in the JSON."""

    if qtype == "SHORT":
        prompt: str = f"""Based on the following text, generate {num_questions} {difficulty} level SHORT ANSWER questions.
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
        response_text = generate_content_with_gemini(model, prompt)
        return _clean_gemini_json(response_text)
    except Exception as e:
        print(f"DEBUG: Error generating questions: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"Failed to generate questions: {str(e)}") from e


@cache_response(timeout=300)
def generate_flashcards_with_gemini(text: str) -> list[dict[str, str]]:
    model: Any = get_gemini_model()
    prompt: str = f"""Based on the following text, generate 10-20 flashcards for studying.
Each flashcard should have a "front" (question/term/concept) and "back" (answer/definition/explanation).
Cover all key concepts.

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"front": "What is ...?", "back": "It is ..."}}]"""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        return _clean_gemini_json(response_text)
    except Exception as e:
        print(f"DEBUG: Error generating flashcards: {e}")
        return []


@cache_response(timeout=300)
def extract_topics_with_gemini(text: str) -> list[dict[str, str]]:
    model: Any = get_gemini_model()
    prompt: str = f"""Analyze the following text and extract the key topics/concepts.
For each, provide a brief explanation.

Text:
{text}

Return ONLY a JSON array, no markdown, no code blocks:
[{{"topic": "Topic Name", "explanation": "Brief explanation"}}]

Extract 5 to 15 topics."""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        return _clean_gemini_json(response_text)
    except Exception as e:
        print(f"DEBUG: Error extracting topics: {e}")
        return []


@cache_response(timeout=300)
def generate_short_notes_with_gemini(text: str) -> str | None:
    model: Any = get_gemini_model()
    prompt: str = f"""Generate concise short notes for studying from this text.
Organize by topic with ## headings and ### subheadings. Use bullet points.

Text:
{text}"""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        return response_text.strip()
    except Exception as e:
        print(f"DEBUG: Error generating notes: {e}")
        return None


def evaluate_answer_with_gemini(
    question_text: str,
    model_answer: str,
    student_answer: str,
    max_marks: int
) -> dict[str, Any]:
    model: Any = get_gemini_model()
    prompt: str = f"""You are an expert teacher evaluating a student's answer.

Question: {question_text}
Model Answer: {model_answer}
Student's Answer: {student_answer}
Maximum Marks: {max_marks}

Evaluate the student's answer and return ONLY a JSON object (no markdown, no code blocks):
{{
    "score": <number out of {max_marks}>,
    "total": {max_marks},
    "strengths": "What the student got right...",
    "weaknesses": "What was missed or incorrect...",
    "suggestions": "How to improve...",
    "model_answer": "{model_answer}"
}}

Be fair but thorough. Give partial marks where appropriate."""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        return _clean_gemini_json(response_text)
    except Exception as e:
        print(f"DEBUG: Error evaluating answer: {e}")
        return {
            "score": 0,
            "total": max_marks,
            "strengths": "Error occurred",
            "weaknesses": str(e),
            "suggestions": "Please try again",
            "model_answer": model_answer
        }


def regenerate_question_with_gemini(
    question: Any,
    topic: str = None,
    difficulty: str = None
) -> dict[str, Any]:
    model: Any = get_gemini_model()
    
    topic = topic or question.topic
    difficulty = difficulty or question.difficulty
    
    prompt: str = f"""Generate 1 {difficulty} level {question.get_type_display_formatted()} question about "{topic}".

Return ONLY a JSON object (not array):
{{"question": "...", "answer": "...", "explanation": "...", "marks": {question.marks}, "type": "{question.question_type}", "bloom": "understand"}}"""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        data = _clean_gemini_json(response_text)
        if isinstance(data, list):
            data = data[0]
        return data
    except Exception as e:
        print(f"DEBUG: Error regenerating question: {e}")
        raise


def generate_quiz_with_gemini(
    text: str,
    num_questions: int = 10,
    difficulty: str = "Medium"
) -> dict[str, Any]:
    model: Any = get_gemini_model()
    
    prompt: str = f"""Generate a complete quiz with {num_questions} {difficulty} level questions from the following text.
Include a mix of:
- Multiple Choice (4 options)
- Short Answer
- True/False
- Numerical/Problem-solving

Return ONLY a JSON object (no markdown, no code blocks):
{{
    "title": "Quiz Title",
    "description": "Brief quiz description",
    "duration_minutes": 30,
    "questions": [
        {{
            "question": "...",
            "answer": "...",
            "type": "short/mcq/true_false/numerical",
            "options": ["A", "B", "C", "D"] (for MCQ only),
            "marks": 1-5,
            "bloom_level": "remember/understand/apply/analyze/evaluate/create"
        }}
    ]
}}

Text:
{text}"""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        return _clean_gemini_json(response_text)
    except Exception as e:
        print(f"DEBUG: Error generating quiz: {e}")
        raise


def suggest_improvements_with_gemini(text: str) -> str | None:
    model: Any = get_gemini_model()
    
    prompt: str = f"""Analyze the following educational content and suggest improvements.
Consider:
1. Clarity and organization
2. Missing important concepts
3. Potential confusion points
4. Engagement strategies
5. Assessment opportunities

Text:
{text}

Provide suggestions in a structured format with ## headings for each category."""

    try:
        response_text = generate_content_with_gemini(model, prompt)
        return response_text.strip()
    except Exception as e:
        print(f"DEBUG: Error suggesting improvements: {e}")
        return None
