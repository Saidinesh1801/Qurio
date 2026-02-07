import os

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

class ValidationError(Exception):
    pass

def validate_file(file):
    if not file:
        raise ValidationError("No file uploaded")
    
    # Check file extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    return ext

def validate_num_questions(num):
    try:
        num = int(num)
        if num < 1 or num > 50:
            raise ValidationError("Number of questions must be between 1 and 50")
        return num
    except (ValueError, TypeError):
        raise ValidationError("Invalid number of questions")

def validate_difficulty(difficulty):
    valid = ['Easy', 'Medium', 'Hard']
    if difficulty not in valid:
        raise ValidationError(f"Invalid difficulty. Must be one of: {', '.join(valid)}")
    return difficulty

def validate_question_type(qtype):
    valid = ['MCQ', 'TF', 'SHORT', 'LONG', 'NUMERICAL', 'MIXED']
    if qtype not in valid:
        raise ValidationError(f"Invalid question type. Must be one of: {', '.join(valid)}")
    return qtype
