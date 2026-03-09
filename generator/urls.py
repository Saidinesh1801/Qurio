from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('features/', views.features, name='features'),
    path('upload/', views.upload, name='upload'),
    path('history/', views.history, name='history'),

    # Preview & Download
    path('preview/', views.preview_questions, name='preview_questions'),
    path('preview/download-pdf/', views.download_preview_pdf, name='download_preview_pdf'),
    path('preview/download-docx/', views.export_docx, name='export_docx'),

    # Share
    path('share/<str:share_id>/', views.share_paper, name='share_paper'),

    # Regenerate & Delete
    path('regenerate-question/<int:question_id>/', views.regenerate_question, name='regenerate_question'),
    path('delete-question/<int:question_id>/', views.delete_question, name='delete_question'),

    # Quiz
    path('quiz/', views.start_quiz, name='start_quiz'),
    path('quiz/<str:session_id>/submit/', views.submit_quiz, name='submit_quiz'),

    # Flashcards
    path('flashcards/', views.flashcards, name='flashcards'),

    # AI Answer Evaluator
    path('evaluate/<int:question_id>/', views.evaluate_answer, name='evaluate_answer'),

    # Analytics
    path('analytics/', views.analytics, name='analytics'),

    # Existing
    path('pdf-topic-generator/', views.pdf_topic_generator, name='pdf_topic_generator'),
    path('short-notes/', views.short_notes, name='short_notes'),
    path('short-notes/download/', views.download_notes_pdf, name='download_notes_pdf'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
]
