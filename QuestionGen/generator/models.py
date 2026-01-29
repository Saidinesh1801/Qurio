from django.db import models

# Create your models here.
from django.db import models

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    text = models.TextField()
    answer = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    marks = models.IntegerField()

    def __str__(self):
        return f"{self.topic} ({self.difficulty}) - {self.marks} Marks"
