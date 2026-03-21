import re
from typing import Any
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, MaxLengthValidator, URLValidator


class InputValidator:
    @staticmethod
    def sanitize_text(text: str, max_length: int = 10000) -> str:
        if not text:
            return ""
        
        sanitized = text.strip()
        
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<iframe[^>]*>.*?</iframe>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
        
        return sanitized[:max_length]

    @staticmethod
    def validate_difficulty(value: str) -> str:
        valid = ['Easy', 'Medium', 'Hard']
        if value not in valid:
            raise ValidationError(f"Difficulty must be one of: {', '.join(valid)}")
        return value

    @staticmethod
    def validate_question_type(value: str) -> str:
        valid = ['short', 'mcq', 'true_false', 'long', 'numerical', 'mixed']
        if value.lower() not in valid:
            raise ValidationError(f"Question type must be one of: {', '.join(valid)}")
        return value.lower()

    @staticmethod
    def validate_bloom_level(value: str) -> str:
        valid = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']
        if value.lower() not in valid:
            raise ValidationError(f"Bloom level must be one of: {', '.join(valid)}")
        return value.lower()

    @staticmethod
    def validate_marks(value: int, min_marks: int = 1, max_marks: int = 100) -> int:
        if not isinstance(value, int):
            raise ValidationError("Marks must be an integer")
        if value < min_marks or value > max_marks:
            raise ValidationError(f"Marks must be between {min_marks} and {max_marks}")
        return value

    @staticmethod
    def validate_num_questions(value: int, min_questions: int = 1, max_questions: int = 100) -> int:
        if not isinstance(value, int):
            raise ValidationError("Number of questions must be an integer")
        if value < min_questions or value > max_questions:
            raise ValidationError(f"Number of questions must be between {min_questions} and {max_questions}")
        return value

    @staticmethod
    def validate_file_type(filename: str, allowed_extensions: list[str] = None) -> str:
        if allowed_extensions is None:
            allowed_extensions = ['.pdf', '.docx', '.txt', '.doc']
        
        ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
        
        if ext not in allowed_extensions:
            raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        return filename

    @staticmethod
    def validate_email(email: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("Invalid email address")
        return email.lower()

    @staticmethod
    def validate_username(username: str) -> str:
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters long")
        if len(username) > 30:
            raise ValidationError("Username must be at most 30 characters long")
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError("Username can only contain letters, numbers, and underscores")
        return username

    @staticmethod
    def validate_password(password: str) -> str:
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")
        if len(password) > 128:
            raise ValidationError("Password must be at most 128 characters long")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character")
        return password

    @staticmethod
    def validate_topic(topic: str, max_length: int = 200) -> str:
        sanitized = InputValidator.sanitize_text(topic, max_length)
        if not sanitized:
            raise ValidationError("Topic cannot be empty")
        return sanitized

    @staticmethod
    def validate_question_text(text: str, max_length: int = 5000) -> str:
        sanitized = InputValidator.sanitize_text(text, max_length)
        if not sanitized:
            raise ValidationError("Question text cannot be empty")
        if len(sanitized) < 5:
            raise ValidationError("Question text must be at least 5 characters")
        return sanitized


def validate_upload_request(request_data: dict[str, Any]) -> dict[str, Any]:
    validated = {}
    
    if 'difficulty' in request_data:
        validated['difficulty'] = InputValidator.validate_difficulty(request_data['difficulty'])
    
    if 'question_type' in request_data:
        validated['question_type'] = InputValidator.validate_question_type(request_data['question_type'])
    
    if 'num_questions' in request_data:
        validated['num_questions'] = InputValidator.validate_num_questions(int(request_data['num_questions']))
    
    if 'topic' in request_data:
        validated['topic'] = InputValidator.validate_topic(request_data['topic'])
    
    if 'text' in request_data:
        validated['text'] = InputValidator.sanitize_text(request_data['text'], max_length=50000)
    
    return validated


def sanitize_html(dangerous_html: str) -> str:
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'a', 'img', 'blockquote', 'code', 'pre'
    ]
    
    allowed_attrs = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title'],
    }
    
    import re
    
    for tag in allowed_tags:
        dangerous_html = re.sub(f'<{tag}(?!\\s)[^>]*>', f'<{tag}>', dangerous_html, flags=re.IGNORECASE)
    
    dangerous_html = re.sub(r'<script[^>]*>.*?</script>', '', dangerous_html, flags=re.IGNORECASE | re.DOTALL)
    dangerous_html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', dangerous_html, flags=re.IGNORECASE | re.DOTALL)
    dangerous_html = re.sub(r'javascript:', '', dangerous_html, flags=re.IGNORECASE)
    dangerous_html = re.sub(r'on\w+\s*=', '', dangerous_html, flags=re.IGNORECASE)
    
    return dangerous_html
