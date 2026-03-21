from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/progress/<str:task_id>/', consumers.ProgressConsumer.as_asgi()),
    path('ws/collaborate/<str:session_id>/', consumers.CollaborationConsumer.as_asgi()),
    path('ws/chat/<int:question_id>/', consumers.ChatConsumer.as_asgi()),
]
