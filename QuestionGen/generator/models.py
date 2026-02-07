from django.db import models

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    
    QUESTION_TYPE_CHOICES = [
        ('MCQ', 'Multiple Choice'),
        ('TF', 'True/False'),
        ('SHORT', 'Short Answer'),
        ('LONG', 'Long Answer'),
        ('NUMERICAL', 'Numerical/Mathematical'),
    ]

    text = models.TextField()
    answer = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE_CHOICES, default='SHORT')
    marks = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} ({self.difficulty}) - {self.marks} Marks"
    
    class Meta:
        ordering = ['-created_at']
