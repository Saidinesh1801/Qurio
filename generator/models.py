from django.db import models
from django.utils import timezone
import uuid

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    TYPE_CHOICES = [
        ('short', 'Short Answer'),
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('long', 'Long Answer'),
        ('numerical', 'Numerical'),
        ('mixed', 'Mixed'),
    ]

    BLOOM_CHOICES = [
        ('remember', 'Remember'),
        ('understand', 'Understand'),
        ('apply', 'Apply'),
        ('analyze', 'Analyze'),
        ('evaluate', 'Evaluate'),
        ('create', 'Create'),
    ]

    text = models.TextField()
    answer = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=200)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='mixed')
    marks = models.IntegerField(default=1)
    bloom_level = models.CharField(max_length=20, choices=BLOOM_CHOICES, default='understand')
    share_id = models.CharField(max_length=36, blank=True, null=True, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.topic} ({self.difficulty}) - {self.marks} Marks"

    class Meta:
        ordering = ['-created_at']


class QuizSession(models.Model):
    session_id = models.CharField(max_length=36, default=uuid.uuid4, unique=True)
    questions = models.ManyToManyField(Question)
    topic = models.CharField(max_length=200)
    score = models.IntegerField(null=True, blank=True)
    total = models.IntegerField(default=0)
    time_taken = models.IntegerField(null=True, blank=True)  # seconds
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Quiz: {self.topic} - {self.score}/{self.total}"


class FlashcardSet(models.Model):
    set_id = models.CharField(max_length=36, default=uuid.uuid4, unique=True)
    topic = models.CharField(max_length=200)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Flashcards: {self.topic}"


class Flashcard(models.Model):
    flashcard_set = models.ForeignKey(FlashcardSet, on_delete=models.CASCADE, related_name='cards')
    front = models.TextField()
    back = models.TextField()
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Card {self.order}: {self.front[:50]}"
