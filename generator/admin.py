from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Question

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    # This displays columns in the admin list view
    list_display = ('topic', 'difficulty', 'marks')
    # This adds a filter sidebar on the right
    list_filter = ('difficulty', 'topic')