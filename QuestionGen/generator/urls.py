from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
]
from django.urls import path
from .views import generate_questions_view

urlpatterns = [
    path('', generate_questions_view, name='generate_questions'),
]
