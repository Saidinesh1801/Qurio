from django.db import models

# Create your models here.
from django.db import models

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    
    TYPE_CHOICES = [
        ('theoretical', 'Theoretical'),
        ('numerical', 'Numerical'),
        ('mixed', 'Mixed'),
    ]

    text = models.TextField()
    answer = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='mixed')
    marks = models.IntegerField()

    def __str__(self):
        return f"{self.topic} ({self.difficulty}) - {self.marks} Marks"
