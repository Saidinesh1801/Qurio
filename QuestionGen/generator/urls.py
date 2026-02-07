from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('features/', views.features, name='features'),
    path('upload/', views.upload, name='upload'),
    path('history/', views.history, name='history'),
    path('pdf-topic-generator/', views.pdf_topic_generator, name='pdf_topic_generator'),
    path('short-notes/', views.short_notes, name='short_notes'),
    path('short-notes/download/', views.download_notes_pdf, name='download_notes_pdf'),
]
