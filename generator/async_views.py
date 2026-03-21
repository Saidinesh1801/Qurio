import asyncio
import uuid
import json
import re
from typing import Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from .models import Question, QuizSession, FlashcardSet, Flashcard, UserProfile, Notification
from .utils import extract_text_from_file
from .generators import (
    generate_questions_with_gemini,
    generate_flashcards_with_gemini,
    extract_topics_with_gemini,
    generate_short_notes_with_gemini,
)
from .consumers import send_progress_update, send_task_complete


@csrf_exempt
def async_generate_questions(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    task_id = str(uuid.uuid4())
    
    study_file = request.FILES.get('study_file')
    pasted_text = request.POST.get('pasted_text', '').strip()
    difficulty = request.POST.get('difficulty', 'Medium')
    num_questions = int(request.POST.get('num_questions', 5))
    question_type = request.POST.get('question_type', 'MIXED')
    
    if study_file:
        text = extract_text_from_file(study_file)
        filename = study_file.name
    elif pasted_text:
        text = pasted_text
        filename = 'Pasted Text'
    else:
        return JsonResponse({'error': 'Please upload a file or paste text'}, status=400)
    
    if not text.strip():
        return JsonResponse({'error': 'Empty content'}, status=400)
    
    try:
        send_progress_update(task_id, 10, 'Starting', 'Initializing question generation...')
        
        send_progress_update(task_id, 30, 'Processing', 'Analyzing study material...')
        
        questions_data = generate_questions_with_gemini(
            text, difficulty, num_questions, question_type
        )
        
        if not questions_data:
            send_task_complete(task_id, False, error='Could not generate questions')
            return JsonResponse({'error': 'Could not generate questions'}, status=500)
        
        send_progress_update(task_id, 60, 'Processing', f'Generated {len(questions_data)} questions...')
        
        saved_questions = _save_questions_async(questions_data, filename, difficulty, question_type, request.user)
        
        send_progress_update(task_id, 90, 'Finalizing', 'Saving questions to database...')
        
        question_ids = ','.join(str(q.id) for q in saved_questions)
        preview_url = f'/preview/?ids={question_ids}'
        
        send_task_complete(task_id, True, {
            'question_ids': question_ids,
            'preview_url': preview_url,
            'count': len(saved_questions),
        })
        
        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'preview_url': preview_url,
        })
        
    except Exception as e:
        send_task_complete(task_id, False, error=str(e))
        return JsonResponse({'error': str(e)}, status=500)


def _save_questions_async(
    questions_data: list[dict[str, Any]],
    topic: str,
    difficulty: str,
    question_type: str,
    user=None
) -> list[Question]:
    from django.db import transaction
    
    share_id = str(uuid.uuid4())
    saved = []
    
    with transaction.atomic():
        for q_data in questions_data:
            q_text = q_data.get('question', '')
            q_answer = q_data.get('answer', '')
            
            if isinstance(q_text, dict):
                q_text = str(q_text)
            if isinstance(q_answer, dict):
                q_answer = '\n'.join(f"{k}: {v}" for k, v in q_answer.items())
            
            q = Question.objects.create(
                user=user,
                text=str(q_text),
                topic=topic,
                difficulty=difficulty,
                marks=q_data.get('marks', 1),
                answer=str(q_answer),
                explanation=q_data.get('explanation', ''),
                question_type=q_data.get('type', question_type.lower()),
                bloom_level=q_data.get('bloom', 'understand'),
                share_id=share_id if not saved else None,
                source_text=q_data.get('source', ''),
            )
            saved.append(q)
    
    if user and hasattr(user, 'profile'):
        user.profile.increment_question_count(len(saved_questions))
    
    return saved


@csrf_exempt
def async_generate_flashcards(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    task_id = str(uuid.uuid4())
    
    study_file = request.FILES.get('study_file')
    pasted_text = request.POST.get('pasted_text', '').strip()
    
    if study_file:
        text = extract_text_from_file(study_file)
        filename = study_file.name
    elif pasted_text:
        text = pasted_text
        filename = 'Pasted Text'
    else:
        return JsonResponse({'error': 'Please upload a file or paste text'}, status=400)
    
    if not text.strip():
        return JsonResponse({'error': 'Empty content'}, status=400)
    
    try:
        send_progress_update(task_id, 20, 'Processing', 'Generating flashcards...')
        
        flashcards_data = generate_flashcards_with_gemini(text)
        
        if not flashcards_data:
            send_task_complete(task_id, False, error='Could not generate flashcards')
            return JsonResponse({'error': 'Could not generate flashcards'}, status=500)
        
        send_progress_update(task_id, 70, 'Processing', f'Creating {len(flashcards_data)} flashcards...')
        
        topic = filename.split('.')[0] if '.' in filename else filename
        fc_set = FlashcardSet.objects.create(
            topic=topic,
            user=request.user if request.user.is_authenticated else None,
        )
        
        cards = []
        for i, c in enumerate(flashcards_data):
            card = Flashcard.objects.create(
                flashcard_set=fc_set,
                front=c.get('front', ''),
                back=c.get('back', ''),
                order=i,
            )
            cards.append({
                'id': card.id,
                'front': card.front,
                'back': card.back,
            })
        
        send_task_complete(task_id, True, {
            'flashcard_set_id': str(fc_set.set_id),
            'cards': cards,
            'count': len(cards),
        })
        
        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'flashcard_set_id': str(fc_set.set_id),
        })
        
    except Exception as e:
        send_task_complete(task_id, False, error=str(e))
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def task_status(request: HttpRequest, task_id: str) -> JsonResponse:
    return JsonResponse({
        'task_id': task_id,
        'status': 'checking',
        'message': 'Use WebSocket for real-time updates',
    })


@login_required
def question_bank_view(request: HttpRequest) -> HttpResponse:
    from django.db.models import Count, Q
    
    banks = QuestionBank.objects.filter(
        Q(user=request.user) | Q(is_public=True)
    ).select_related('user').prefetch_related('tags', 'questions').annotate(
        question_count=Count('questions')
    )
    
    return render(request, 'question_bank.html', {
        'banks': banks,
    })


@login_required
def create_question_bank(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_public = request.POST.get('is_public', 'off') == 'on'
        
        if not name:
            return render(request, 'create_question_bank.html', {'error': 'Name is required'})
        
        bank = QuestionBank.objects.create(
            name=name,
            description=description,
            user=request.user,
            is_public=is_public,
        )
        
        return redirect('question_bank_detail', bank_id=bank.id)
    
    return render(request, 'create_question_bank.html')


@login_required
def question_bank_detail(request: HttpRequest, bank_id: int) -> HttpResponse:
    from django.shortcuts import get_object_or_404
    
    bank = get_object_or_404(
        QuestionBank.objects.prefetch_related('questions', 'tags'),
        Q(id=bank_id) & (Q(user=request.user) | Q(is_public=True))
    )
    
    questions = bank.questions.all()
    
    return render(request, 'question_bank_detail.html', {
        'bank': bank,
        'questions': questions,
    })


def shared_bank_view(request: HttpRequest, share_id: str) -> HttpResponse:
    from django.shortcuts import get_object_or_404
    
    bank = get_object_or_404(
        QuestionBank.objects.prefetch_related('questions', 'tags'),
        share_id=share_id
    )
    
    bank.view_count += 1
    bank.save(update_fields=['view_count'])
    
    return render(request, 'shared_bank.html', {
        'bank': bank,
        'questions': bank.questions.all(),
    })


@login_required
def study_plan_view(request: HttpRequest) -> HttpResponse:
    from django.db.models import Count
    
    plans = StudyPlan.objects.filter(user=request.user).prefetch_related(
        'flashcard_sets', 'question_banks'
    ).annotate(
        total_cards=Count('flashcard_sets__cards'),
        total_questions=Count('question_banks__questions'),
    )
    
    return render(request, 'study_plan.html', {
        'plans': plans,
    })


@login_required
def create_study_plan(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        frequency = request.POST.get('frequency', 'daily')
        target_daily_cards = int(request.POST.get('target_daily_cards', 20))
        target_daily_questions = int(request.POST.get('target_daily_questions', 10))
        start_date = request.POST.get('start_date')
        
        if not title or not start_date:
            return render(request, 'create_study_plan.html', {'error': 'Title and start date required'})
        
        plan = StudyPlan.objects.create(
            user=request.user,
            title=title,
            description=description,
            frequency=frequency,
            target_daily_cards=target_daily_cards,
            target_daily_questions=target_daily_questions,
            start_date=start_date,
        )
        
        return redirect('study_plan_detail', plan_id=plan.id)
    
    return render(request, 'create_study_plan.html')


@login_required
def notifications_view(request: HttpRequest) -> HttpResponse:
    notifications = Notification.objects.filter(user=request.user)[:50]
    
    return render(request, 'notifications.html', {
        'notifications': notifications,
    })


@login_required
def mark_notification_read(request: HttpRequest, notification_id: int) -> JsonResponse:
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    profile = request.user.profile
    
    recent_questions = Question.objects.filter(user=request.user)[:10]
    recent_quizzes = QuizSession.objects.filter(user=request.user, completed=True)[:10]
    
    return render(request, 'profile.html', {
        'profile': profile,
        'recent_questions': recent_questions,
        'recent_quizzes': recent_quizzes,
    })


from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect


@login_required
def update_profile(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        profile = request.user.profile
        
        profile.role = request.POST.get('role', profile.role)
        profile.institution = request.POST.get('institution', profile.institution)
        profile.bio = request.POST.get('bio', profile.bio)
        profile.theme = request.POST.get('theme', profile.theme)
        profile.email_notifications = request.POST.get('email_notifications', 'on') == 'on'
        
        profile.save()
        
        return redirect('profile')
    
    return redirect('profile')
