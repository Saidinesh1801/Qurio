import asyncio
import json
import uuid
from typing import Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User


class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.room_group_name = f'progress_{self.task_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        pass
    
    async def progress_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'progress',
            'progress': event['progress'],
            'status': event['status'],
            'message': event.get('message', ''),
        }))
    
    async def task_complete(self, event):
        await self.send(text_data=json.dumps({
            'type': 'complete',
            'success': event['success'],
            'data': event.get('data', {}),
            'error': event.get('error', ''),
        }))
    
    async def task_error(self, event):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': event['error'],
        }))


class CollaborationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.user = self.scope.get('user')
        self.room_group_name = f'collab_{self.session_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user': self.user.username if self.user else 'Anonymous',
            }
        )
    
    async def disconnect(self, close_code):
        if self.user:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user': self.user.username,
                }
            )
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'cursor_move':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'cursor_update',
                    'user': self.user.username if self.user else 'Anonymous',
                    'position': data.get('position'),
                }
            )
        elif action == 'selection':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'selection_update',
                    'user': self.user.username if self.user else 'Anonymous',
                    'selection': data.get('selection'),
                }
            )
        elif action == 'edit':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'content_edit',
                    'user': self.user.username if self.user else 'Anonymous',
                    'edit': data.get('edit'),
                }
            )
    
    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user': event['user'],
        }))
    
    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user': event['user'],
        }))
    
    async def cursor_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'cursor_update',
            'user': event['user'],
            'position': event['position'],
        }))
    
    async def selection_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'selection_update',
            'user': event['user'],
            'selection': event['selection'],
        }))
    
    async def content_edit(self, event):
        await self.send(text_data=json.dumps({
            'type': 'content_edit',
            'user': event['user'],
            'edit': event['edit'],
        }))


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.question_id = self.scope['url_route']['kwargs']['question_id']
        self.room_group_name = f'chat_{self.question_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '')
        user = self.scope.get('user')
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': user.username if user else 'Anonymous',
            }
        )
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'user': event['user'],
        }))


def send_progress_update(task_id: str, progress: int, status: str, message: str = ''):
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'progress_{task_id}',
        {
            'type': 'progress_update',
            'progress': progress,
            'status': status,
            'message': message,
        }
    )


def send_task_complete(task_id: str, success: bool, data: dict = None, error: str = ''):
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'progress_{task_id}',
        {
            'type': 'task_complete',
            'success': success,
            'data': data or {},
            'error': error,
        }
    )
