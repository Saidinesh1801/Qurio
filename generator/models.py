from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#3498db")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.name.lower().replace(' ', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


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

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    text = models.TextField()
    answer = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=200)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='mixed')
    marks = models.IntegerField(default=1)
    bloom_level = models.CharField(max_length=20, choices=BLOOM_CHOICES, default='understand')
    tags = models.ManyToManyField(Tag, blank=True, related_name='questions')
    share_id = models.CharField(max_length=36, blank=True, null=True, unique=True, db_index=True)
    source_text = models.TextField(blank=True, null=True, help_text="Original text from which question was generated")
    is_favorite = models.BooleanField(default=False)
    times_used = models.IntegerField(default=0)
    avg_quiz_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.topic} ({self.difficulty}) - {self.marks} Marks"

    def get_type_display_formatted(self):
        return dict(self.TYPE_CHOICES).get(self.question_type, 'Unknown')

    def get_difficulty_display_formatted(self):
        return dict(self.DIFFICULTY_CHOICES).get(self.difficulty, 'Unknown')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['topic', 'difficulty']),
            models.Index(fields=['question_type', 'bloom_level']),
            models.Index(fields=['-created_at']),
        ]


class QuestionBank(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='question_banks')
    questions = models.ManyToManyField(Question, blank=True, related_name='question_banks')
    tags = models.ManyToManyField(Tag, blank=True, related_name='question_banks')
    is_public = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    download_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_question_count(self):
        return self.questions.count()

    class Meta:
        verbose_name_plural = "Question Banks"
        ordering = ['-created_at']


class QuizSession(models.Model):
    session_id = models.CharField(max_length=36, default=uuid.uuid4, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='quiz_sessions')
    questions = models.ManyToManyField(Question, related_name='quiz_sessions')
    topic = models.CharField(max_length=200)
    score = models.IntegerField(null=True, blank=True)
    total = models.IntegerField(default=0)
    time_taken = models.IntegerField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    difficulty = models.CharField(max_length=10, choices=Question.DIFFICULTY_CHOICES, default='Medium')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Quiz: {self.topic} - {self.score}/{self.total}"

    def get_percentage(self):
        if self.total > 0:
            return round((self.score / self.total) * 100, 1)
        return 0

    class Meta:
        ordering = ['-created_at']


class FlashcardSet(models.Model):
    set_id = models.CharField(max_length=36, default=uuid.uuid4, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='flashcard_sets')
    topic = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='flashcard_sets')
    is_favorite = models.BooleanField(default=False)
    last_studied = models.DateTimeField(null=True, blank=True)
    study_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Flashcards: {self.topic}"

    class Meta:
        ordering = ['-created_at']


class Flashcard(models.Model):
    flashcard_set = models.ForeignKey(FlashcardSet, on_delete=models.CASCADE, related_name='cards')
    front = models.TextField()
    back = models.TextField()
    order = models.IntegerField(default=0)
    times_reviewed = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    last_reviewed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Card {self.order}: {self.front[:50]}"

    def get_accuracy(self):
        if self.times_reviewed > 0:
            return round((self.correct_count / self.times_reviewed) * 100, 1)
        return 0


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('institution', 'Institution'),
        ('admin', 'Admin'),
    ]

    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    institution = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='auto')
    email_verified = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    api_rate_limit = models.IntegerField(default=100)
    daily_question_limit = models.IntegerField(default=50)
    questions_generated_today = models.IntegerField(default=0)
    last_generation_date = models.DateField(null=True, blank=True)
    total_questions_generated = models.IntegerField(default=0)
    total_quizzes_taken = models.IntegerField(default=0)
    average_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"

    def reset_daily_questions(self):
        from datetime import date
        if self.last_generation_date != date.today():
            self.questions_generated_today = 0
            self.last_generation_date = date.today()
            self.save()

    def can_generate_question(self, count=1):
        self.reset_daily_questions()
        return (self.questions_generated_today + count) <= self.daily_question_limit

    def increment_question_count(self, count=1):
        self.reset_daily_questions()
        self.questions_generated_today += count
        self.total_questions_generated += count
        self.save()


class SharedAccess(models.Model):
    ACCESS_LEVEL_CHOICES = [
        ('view', 'View Only'),
        ('edit', 'Edit'),
        ('admin', 'Full Access'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_access')
    question_bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name='shared_access')
    access_level = models.CharField(max_length=10, choices=ACCESS_LEVEL_CHOICES, default='view')
    shared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='shared_by')
    shared_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.question_bank.name} ({self.access_level})"

    class Meta:
        unique_together = ['user', 'question_bank']


class StudyPlan(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('custom', 'Custom'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_plans')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    flashcard_sets = models.ManyToManyField(FlashcardSet, blank=True, related_name='study_plans')
    question_banks = models.ManyToManyField(QuestionBank, blank=True, related_name='study_plans')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    target_daily_cards = models.IntegerField(default=20)
    target_daily_questions = models.IntegerField(default=10)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    streak_count = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_study_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Study Plan: {self.title}"

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    TYPE_CHOICES = [
        ('quiz_result', 'Quiz Result'),
        ('shared_content', 'Shared Content'),
        ('weekly_summary', 'Weekly Summary'),
        ('achievement', 'Achievement'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username}: {self.title}"

    class Meta:
        ordering = ['-created_at']


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
