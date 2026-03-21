"""
API Documentation for Question Generation App
=============================================

Base URL: /api/v1/

Authentication
--------------
Most endpoints require authentication via session or token.
Include the following in your requests:
    - Cookie: sessionid=<your_session_id>
    - Or Header: Authorization: Token <your_token>

Rate Limiting
-------------
- Default: 10 requests per minute
- Headers returned:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Remaining requests in window
    - Retry-After: Seconds to wait (when rate limited)

Response Format
---------------
All responses are JSON with the following structure:
{
    "success": true/false,
    "data": {...} or [...],
    "error": "Error message" (on failure),
    "count": N (for list responses)
}

Endpoints
--------

1. Generate Questions
   POST /api/v1/generate-questions/
   
   Body (multipart/form-data):
   - study_file: File (optional) - PDF, DOCX, or TXT
   - pasted_text: String (optional) - Raw text content
   - difficulty: String - Easy/Medium/Hard
   - num_questions: Integer (default: 5)
   - question_type: String - SHORT/MCQ/TF/LONG/NUMERICAL/MIXED
   
   Response:
   {
       "success": true,
       "data": {
           "questions": [...],
           "count": 5
       }
   }

2. Generate Flashcards
   POST /api/v1/generate-flashcards/
   
   Body (multipart/form-data):
   - study_file: File (optional)
   - pasted_text: String (optional)
   
   Response:
   {
       "success": true,
       "data": {
           "flashcards": [...],
           "count": 15
       }
   }

3. Extract Topics
   POST /api/v1/extract-topics/
   
   Body (multipart/form-data):
   - study_file: File (optional)
   - pasted_text: String (optional)
   
   Response:
   {
       "success": true,
       "data": {
           "topics": [
               {"topic": "...", "explanation": "..."}
           ],
           "count": 10
       }
   }

4. Generate Short Notes
   POST /api/v1/short-notes/
   
   Body (multipart/form-data):
   - study_file: File (optional)
   - pasted_text: String (optional)
   
   Response:
   {
       "success": true,
       "data": {
           "notes": "## Topic\n- Point 1\n..."
       }
   }

5. Quiz Management
   GET /api/v1/quiz/
   - Returns list of user's quiz sessions
   
   POST /api/v1/quiz/
   - Create new quiz session
   
   GET /api/v1/quiz/<session_id>/
   - Get quiz details
   
   POST /api/v1/quiz/<session_id>/submit/
   - Submit quiz answers

6. Question Bank
   GET /api/v1/banks/
   - List user's question banks
   
   POST /api/v1/banks/
   - Create new question bank
   
   GET /api/v1/banks/<id>/
   - Get bank details
   
   PUT /api/v1/banks/<id>/
   - Update bank
   
   DELETE /api/v1/banks/<id>/
   - Delete bank

7. Study Plans
   GET /api/v1/plans/
   - List study plans
   
   POST /api/v1/plans/
   - Create study plan
   
   GET /api/v1/plans/<id>/
   - Get plan details
   
   POST /api/v1/plans/<id>/update-progress/
   - Update progress

8. Notifications
   GET /api/v1/notifications/
   - List notifications
   
   POST /api/v1/notifications/<id>/read/
   - Mark as read

WebSocket Endpoints
-------------------

1. Progress Updates
   ws://host/ws/progress/<task_id>/
   
   Message Types:
   - progress: {progress: 50, status: "Processing", message: "..."}
   - complete: {success: true, data: {...}}
   - error: {error: "..."}

2. Real-time Collaboration
   ws://host/ws/collaborate/<session_id>/
   
   Actions:
   - cursor_move: {action: "cursor_move", position: {...}}
   - selection: {action: "selection", selection: {...}}
   - edit: {action: "edit", edit: {...}}

Error Codes
-----------
400: Bad Request - Invalid input
401: Unauthorized - Authentication required
403: Forbidden - Insufficient permissions
404: Not Found - Resource doesn't exist
429: Too Many Requests - Rate limit exceeded
500: Server Error - Something went wrong

Examples
--------

cURL:
```bash
# Generate questions
curl -X POST http://localhost:8000/api/v1/generate-questions/ \
  -H "Cookie: sessionid=..." \
  -F "pasted_text=Python is a programming language..." \
  -F "difficulty=Easy" \
  -F "num_questions=5" \
  -F "question_type=SHORT"

# Python requests:
import requests

response = requests.post(
    'http://localhost:8000/api/v1/generate-questions/',
    data={
        'pasted_text': 'Python is a programming language...',
        'difficulty': 'Easy',
        'num_questions': 5,
        'question_type': 'SHORT'
    },
    cookies={'sessionid': '...'}
)
print(response.json())

# JavaScript fetch:
fetch('/api/v1/generate-questions/', {
    method: 'POST',
    body: new FormData(),
    body.append('pasted_text', 'Python is a programming language...'),
    body.append('difficulty', 'Easy'),
    credentials: 'include'
})
.then(res => res.json())
.then(data => console.log(data));
```
"""

API_VERSION = 'v1'
API_TITLE = 'Question Generation API'
API_DESCRIPTION = '''
A comprehensive API for generating educational questions, flashcards, and study materials using AI.

## Features

- **Question Generation**: Create various types of questions (MCQ, Short Answer, True/False, etc.)
- **Flashcard Generation**: Automatically generate study flashcards from content
- **Topic Extraction**: Identify key topics from study materials
- **Short Notes**: Generate condensed study notes
- **Quiz Management**: Create and manage quizzes with progress tracking
- **Question Banks**: Organize questions into categorized banks
- **Study Plans**: Create personalized study schedules

## Rate Limits

- Default: 10 requests per minute
- Extended: Available for premium users

## Support

For API support, contact: support@questiongen.example.com
'''
