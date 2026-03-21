import time
import hashlib
from functools import wraps
from typing import Any, Callable
from django.http import JsonResponse, HttpRequest


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, identifier: str) -> tuple[bool, int, int]:
        current_time = time.time()
        
        if identifier not in self._requests:
            self._requests[identifier] = []
        
        self._requests[identifier] = [
            t for t in self._requests[identifier]
            if current_time - t < self.window_seconds
        ]
        
        remaining = self.max_requests - len(self._requests[identifier])
        
        if len(self._requests[identifier]) < self.max_requests:
            self._requests[identifier].append(current_time)
            return True, remaining - 1, 0
        
        wait_time = int(self._requests[identifier][0] + self.window_seconds - current_time)
        return False, 0, wait_time


rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


def rate_limit(max_requests: int = 10, window_seconds: int = 60) -> Callable:
    def decorator(func: Callable) -> Callable:
        limiter = RateLimiter(max_requests, window_seconds)
        
        @wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse | Any:
            client_ip = get_client_ip(request)
            identifier = hashlib.md5(f"{client_ip}:{request.path}".encode()).hexdigest()
            
            allowed, remaining, wait_time = limiter.is_allowed(identifier)
            
            if not allowed:
                response = JsonResponse(
                    {'error': 'Rate limit exceeded', 'retry_after': wait_time},
                    status=429
                )
                response['Retry-After'] = str(wait_time)
                response['X-RateLimit-Remaining'] = '0'
                return response
            
            response = func(request, *args, **kwargs)
            
            if isinstance(response, JsonResponse):
                response['X-RateLimit-Remaining'] = str(max(0, remaining))
                response['X-RateLimit-Limit'] = str(max_requests)
            
            return response
        return wrapper
    return decorator


def get_client_ip(request: HttpRequest) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def api_view(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        if request.method not in ('GET', 'POST'):
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        try:
            return func(request, *args, **kwargs)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return wrapper


@rate_limit(max_requests=10, window_seconds=60)
def api_generate_questions(request: HttpRequest) -> JsonResponse:
    from django.http import JsonResponse
    from .generators import generate_questions_with_gemini
    from .utils import extract_text_from_file
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    study_file = request.FILES.get('study_file')
    pasted_text = request.POST.get('pasted_text', '').strip()
    difficulty = request.POST.get('difficulty', 'Medium')
    num_questions = int(request.POST.get('num_questions', 5))
    question_type = request.POST.get('question_type', 'MIXED')
    
    if study_file:
        text = extract_text_from_file(study_file)
    elif pasted_text:
        text = pasted_text
    else:
        return JsonResponse({'error': 'Please upload a file or paste text'}, status=400)
    
    if not text.strip():
        return JsonResponse({'error': 'Empty content'}, status=400)
    
    questions = generate_questions_with_gemini(text, difficulty, num_questions, question_type)
    
    if not questions:
        return JsonResponse({'error': 'Could not generate questions'}, status=500)
    
    return JsonResponse({
        'success': True,
        'questions': questions,
        'count': len(questions)
    })


@rate_limit(max_requests=10, window_seconds=60)
def api_generate_flashcards(request: HttpRequest) -> JsonResponse:
    from django.http import JsonResponse
    from .generators import generate_flashcards_with_gemini
    from .utils import extract_text_from_file
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    study_file = request.FILES.get('study_file')
    pasted_text = request.POST.get('pasted_text', '').strip()
    
    if study_file:
        text = extract_text_from_file(study_file)
    elif pasted_text:
        text = pasted_text
    else:
        return JsonResponse({'error': 'Please upload a file or paste text'}, status=400)
    
    if not text.strip():
        return JsonResponse({'error': 'Empty content'}, status=400)
    
    flashcards = generate_flashcards_with_gemini(text)
    
    if not flashcards:
        return JsonResponse({'error': 'Could not generate flashcards'}, status=500)
    
    return JsonResponse({
        'success': True,
        'flashcards': flashcards,
        'count': len(flashcards)
    })


@rate_limit(max_requests=10, window_seconds=60)
def api_extract_topics(request: HttpRequest) -> JsonResponse:
    from django.http import JsonResponse
    from .generators import extract_topics_with_gemini
    from .utils import extract_text_from_file
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    study_file = request.FILES.get('study_file')
    pasted_text = request.POST.get('pasted_text', '').strip()
    
    if study_file:
        text = extract_text_from_file(study_file)
    elif pasted_text:
        text = pasted_text
    else:
        return JsonResponse({'error': 'Please upload a file or paste text'}, status=400)
    
    if not text.strip():
        return JsonResponse({'error': 'Empty content'}, status=400)
    
    topics = extract_topics_with_gemini(text)
    
    if not topics:
        return JsonResponse({'error': 'Could not extract topics'}, status=500)
    
    return JsonResponse({
        'success': True,
        'topics': topics,
        'count': len(topics)
    })


@rate_limit(max_requests=10, window_seconds=60)
def api_short_notes(request: HttpRequest) -> JsonResponse:
    from django.http import JsonResponse
    from .generators import generate_short_notes_with_gemini
    from .utils import extract_text_from_file
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    study_file = request.FILES.get('study_file')
    pasted_text = request.POST.get('pasted_text', '').strip()
    
    if study_file:
        text = extract_text_from_file(study_file)
    elif pasted_text:
        text = pasted_text
    else:
        return JsonResponse({'error': 'Please upload a file or paste text'}, status=400)
    
    if not text.strip():
        return JsonResponse({'error': 'Empty content'}, status=400)
    
    notes = generate_short_notes_with_gemini(text)
    
    if not notes:
        return JsonResponse({'error': 'Could not generate notes'}, status=500)
    
    return JsonResponse({
        'success': True,
        'notes': notes
    })
