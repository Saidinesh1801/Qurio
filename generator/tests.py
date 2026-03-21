import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
import json
from unittest.mock import patch, MagicMock
from generator.models import Question, QuizSession, FlashcardSet, Flashcard, Tag, QuestionBank


class QuestionModelTest(TestCase):
    def setUp(self):
        self.question = Question.objects.create(
            text="What is Python?",
            answer="A programming language",
            topic="Programming",
            difficulty="Easy",
            question_type="short",
            marks=2
        )

    def test_question_creation(self):
        self.assertEqual(self.question.text, "What is Python?")
        self.assertEqual(self.question.difficulty, "Easy")
        self.assertEqual(self.question.marks, 2)

    def test_question_str_representation(self):
        expected = "Programming (Easy) - 2 Marks"
        self.assertEqual(str(self.question), expected)

    def test_question_default_ordering(self):
        q2 = Question.objects.create(
            text="What is Django?",
            topic="Programming",
            difficulty="Medium",
            question_type="short"
        )
        questions = Question.objects.all()
        self.assertEqual(questions[0], q2)

    def test_question_with_share_id(self):
        question = Question.objects.create(
            text="Shareable question",
            topic="Test",
            difficulty="Easy",
            question_type="short",
            share_id="test-share-id"
        )
        self.assertEqual(question.share_id, "test-share-id")

    def test_question_with_bloom_level(self):
        self.assertEqual(self.question.bloom_level, "understand")


class QuizSessionModelTest(TestCase):
    def setUp(self):
        self.question = Question.objects.create(
            text="Test question",
            topic="Test",
            difficulty="Easy",
            question_type="short"
        )
        self.session = QuizSession.objects.create(
            topic="Test Quiz",
            total=1
        )
        self.session.questions.add(self.question)

    def test_quiz_session_creation(self):
        self.assertEqual(self.session.topic, "Test Quiz")
        self.assertEqual(self.session.total, 1)
        self.assertFalse(self.session.completed)

    def test_quiz_session_str_representation(self):
        self.session.score = 1
        self.session.save()
        expected = "Quiz: Test Quiz - 1/1"
        self.assertEqual(str(self.session), expected)

    def test_quiz_session_completion(self):
        self.session.score = 1
        self.session.completed = True
        self.session.time_taken = 120
        self.session.save()
        self.assertTrue(self.session.completed)
        self.assertEqual(self.session.time_taken, 120)


class FlashcardModelTest(TestCase):
    def setUp(self):
        self.flashcard_set = FlashcardSet.objects.create(topic="Python Basics")
        self.flashcard = Flashcard.objects.create(
            flashcard_set=self.flashcard_set,
            front="What is a variable?",
            back="A container for storing data",
            order=0
        )

    def test_flashcard_creation(self):
        self.assertEqual(self.flashcard.front, "What is a variable?")
        self.assertEqual(self.flashcard.order, 0)

    def test_flashcard_ordering(self):
        Flashcard.objects.create(
            flashcard_set=self.flashcard_set,
            front="What is a function?",
            back="A reusable block of code",
            order=1
        )
        cards = Flashcard.objects.filter(flashcard_set=self.flashcard_set)
        self.assertEqual(cards[0].front, "What is a variable?")
        self.assertEqual(cards[1].front, "What is a function?")

    def test_flashcard_cascade_delete(self):
        card_id = self.flashcard.id
        self.flashcard_set.delete()
        self.assertFalse(Flashcard.objects.filter(id=card_id).exists())


class TagModelTest(TestCase):
    def test_tag_creation(self):
        tag = Tag.objects.create(name="Python", color="#3498db")
        self.assertEqual(tag.name, "Python")
        self.assertEqual(tag.slug, "python")

    def test_tag_uniqueness(self):
        Tag.objects.create(name="Python")
        with self.assertRaises(Exception):
            Tag.objects.create(name="Python")

    def test_tag_str_representation(self):
        tag = Tag.objects.create(name="JavaScript")
        self.assertEqual(str(tag), "JavaScript")


class QuestionBankModelTest(TestCase):
    def setUp(self):
        self.bank = QuestionBank.objects.create(
            name="Programming Questions",
            description="Collection of programming questions",
            is_public=True
        )
        self.tag = Tag.objects.create(name="Python")
        self.question = Question.objects.create(
            text="Test",
            topic="Test",
            difficulty="Easy",
            question_type="short"
        )
        self.bank.questions.add(self.question)
        self.bank.tags.add(self.tag)

    def test_question_bank_creation(self):
        self.assertEqual(self.bank.name, "Programming Questions")
        self.assertEqual(self.bank.questions.count(), 1)
        self.assertEqual(self.bank.tags.count(), 1)

    def test_question_bank_str_representation(self):
        self.assertEqual(str(self.bank), "Programming Questions")

    def test_question_bank_visibility(self):
        self.assertTrue(self.bank.is_public)
        self.bank.is_public = False
        self.bank.save()
        self.assertFalse(self.bank.is_public)


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.question = Question.objects.create(
            text="What is Python?",
            answer="A programming language",
            topic="Programming",
            difficulty="Easy",
            question_type="short",
            marks=2
        )

    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_features_view(self):
        response = self.client.get(reverse('features'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'features.html')

    def test_upload_view_get(self):
        response = self.client.get(reverse('upload'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'upload.html')

    def test_history_view(self):
        response = self.client.get(reverse('history'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('questions', response.context)

    def test_preview_questions_view(self):
        url = f"{reverse('preview_questions')}?ids={self.question.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('questions', response.context)
        self.assertEqual(response.context['topic'], 'Programming')

    def test_preview_questions_empty_ids(self):
        response = self.client.get(reverse('preview_questions'))
        self.assertEqual(response.status_code, 302)

    def test_preview_questions_no_questions_found(self):
        url = f"{reverse('preview_questions')}?ids=99999"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_flashcards_view(self):
        response = self.client.get(reverse('flashcards'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'flashcards.html')

    def test_analytics_view(self):
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_questions', response.context)

    def test_short_notes_view(self):
        response = self.client.get(reverse('short_notes'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'short_notes.html')

    def test_pdf_topic_generator_view(self):
        response = self.client.get(reverse('pdf_topic_generator'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pdf_topic_generator.html')


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_view_get(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_login_view_post_valid(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)

    def test_login_view_post_invalid(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)

    def test_signup_view_get(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'signup.html')

    def test_signup_view_post(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'password1': 'complexpass123!',
            'password2': 'complexpass123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_logout_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_login_redirect(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        }, follow=True)
        self.assertEqual(response.redirect_chain[-1], ('/', 302))


class ProtectedViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_quiz_view_requires_authentication(self):
        response = self.client.get(reverse('start_quiz'))
        self.assertEqual(response.status_code, 302)

    def test_analytics_view_requires_authentication(self):
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 302)


class APIViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_api_generate_questions_get_not_allowed(self):
        response = self.client.get(reverse('api_generate_questions'))
        self.assertEqual(response.status_code, 405)

    def test_api_generate_flashcards_get_not_allowed(self):
        response = self.client.get(reverse('api_generate_flashcards'))
        self.assertEqual(response.status_code, 405)

    def test_api_extract_topics_get_not_allowed(self):
        response = self.client.get(reverse('api_extract_topics'))
        self.assertEqual(response.status_code, 405)

    def test_api_short_notes_get_not_allowed(self):
        response = self.client.get(reverse('api_short_notes'))
        self.assertEqual(response.status_code, 405)


class FileUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_upload_txt_file(self):
        content = b"This is a test document about Python programming."
        file = SimpleUploadedFile(
            "test.txt",
            content,
            content_type="text/plain"
        )
        response = self.client.post(reverse('upload'), {
            'study_file': file,
            'difficulty': 'Easy',
            'num_questions': 5,
            'question_type': 'SHORT'
        })
        self.assertIn(response.status_code, [200, 302, 400])

    def test_upload_empty_text(self):
        response = self.client.post(reverse('upload'), {
            'pasted_text': '',
            'difficulty': 'Easy',
            'num_questions': 5,
            'question_type': 'SHORT'
        })
        self.assertIn(response.status_code, [200, 400])


class UtilityFunctionTests(TestCase):
    def test_extract_text_from_pdf(self):
        from generator.utils import extract_text_from_file
        content = b"%PDF-1.4 test content"
        file = SimpleUploadedFile("test.pdf", content, content_type="application/pdf")
        with self.assertRaises(Exception):
            extract_text_from_file(file)

    def test_extract_text_from_unsupported_file(self):
        from generator.utils import extract_text_from_file
        content = b"test"
        file = SimpleUploadedFile("test.xyz", content, content_type="application/octet-stream")
        with self.assertRaises(ValueError):
            extract_text_from_file(file)


class PDFGenerationTests(TestCase):
    def setUp(self):
        self.question = Question.objects.create(
            text="What is Python?",
            answer="A programming language",
            topic="Programming",
            difficulty="Easy",
            question_type="short",
            marks=2
        )

    def test_generate_pdf_file(self):
        from generator.utils import generate_pdf_file
        buffer = generate_pdf_file([self.question], "Test", include_answers=True)
        self.assertIsInstance(buffer, BytesIO)
        buffer.seek(0)
        self.assertGreater(len(buffer.read()), 0)

    def test_generate_professional_pdf(self):
        from generator.utils import generate_professional_pdf
        buffer = generate_professional_pdf(
            [self.question], "Test", include_answers=True,
            institution="Test University", duration="2 hours"
        )
        self.assertIsInstance(buffer, BytesIO)

    def test_generate_docx_file(self):
        from generator.utils import generate_docx_file
        buffer = generate_docx_file([self.question], "Test", include_answers=True)
        self.assertIsInstance(buffer, BytesIO)


class ValidatorsTest(TestCase):
    def test_minimum_length_validator(self):
        from generator.validators import MinimumLengthValidator
        from django.core.exceptions import ValidationError
        
        validator = MinimumLengthValidator(min_length=8)
        with self.assertRaises(ValidationError):
            validator.validate("short")
        self.assertIsNone(validator.validate("longpassword"))
        self.assertIn("at least 8 characters", validator.get_help_text())

    def test_uppercase_validator(self):
        from generator.validators import UppercaseValidator
        from django.core.exceptions import ValidationError
        
        validator = UppercaseValidator()
        with self.assertRaises(ValidationError):
            validator.validate("nouppercase")
        self.assertIsNone(validator.validate("HasUppercase"))

    def test_lowercase_validator(self):
        from generator.validators import LowercaseValidator
        from django.core.exceptions import ValidationError
        
        validator = LowercaseValidator()
        with self.assertRaises(ValidationError):
            validator.validate("NOLOWERCASE")
        self.assertIsNone(validator.validate("haslowercase"))

    def test_digit_validator(self):
        from generator.validators import DigitValidator
        from django.core.exceptions import ValidationError
        
        validator = DigitValidator()
        with self.assertRaises(ValidationError):
            validator.validate("nospaceschar")
        self.assertIsNone(validator.validate("has123"))

    def test_special_character_validator(self):
        from generator.validators import SpecialCharacterValidator
        from django.core.exceptions import ValidationError
        
        validator = SpecialCharacterValidator()
        with self.assertRaises(ValidationError):
            validator.validate("nospaceschar")
        self.assertIsNone(validator.validate("has!@#$"))

    def test_common_password_validator(self):
        from generator.validators import CommonPasswordValidator
        from django.core.exceptions import ValidationError
        
        validator = CommonPasswordValidator()
        with self.assertRaises(ValidationError):
            validator.validate("password")
        self.assertIsNone(validator.validate("MyV3ryStr0ngP@ss!"))

    def test_numeric_password_validator(self):
        from generator.validators import NumericPasswordValidator
        from django.core.exceptions import ValidationError
        
        validator = NumericPasswordValidator()
        with self.assertRaises(ValidationError):
            validator.validate("12345678")
        self.assertIsNone(validator.validate("abc123def"))


class RateLimiterTest(TestCase):
    def test_rate_limiter_allows_requests_under_limit(self):
        from generator.api import RateLimiter
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        for _ in range(5):
            allowed, remaining, wait = limiter.is_allowed("test_ip")
            self.assertTrue(allowed)

    def test_rate_limiter_blocks_requests_over_limit(self):
        from generator.api import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        limiter.is_allowed("test_ip")
        limiter.is_allowed("test_ip")
        allowed, remaining, wait = limiter.is_allowed("test_ip")
        
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        self.assertGreater(wait, 0)

    def test_rate_limiter_different_identifiers(self):
        from generator.api import RateLimiter
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        self.assertTrue(limiter.is_allowed("ip1")[0])
        self.assertTrue(limiter.is_allowed("ip2")[0])
        self.assertTrue(limiter.is_allowed("ip3")[0])


class CacheDecoratorTests(TestCase):
    def test_cache_response_decorator(self):
        from generator.generators import cache_response
        
        call_count = 0
        
        @cache_response(timeout=60)
        def test_func(text):
            nonlocal call_count
            call_count += 1
            return f"Processed: {text}"
        
        result1 = test_func("hello")
        result2 = test_func("hello")
        result3 = test_func("world")
        
        self.assertEqual(call_count, 2)
        self.assertEqual(result1, result2)
        self.assertNotEqual(result1, result3)


class SharePaperViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.question = Question.objects.create(
            text="Shared question",
            topic="Test",
            difficulty="Easy",
            question_type="short",
            share_id="test-share-123"
        )

    def test_share_paper_valid(self):
        response = self.client.get(
            reverse('share_paper', kwargs={'share_id': 'test-share-123'})
        )
        self.assertEqual(response.status_code, 200)

    def test_share_paper_invalid(self):
        response = self.client.get(
            reverse('share_paper', kwargs={'share_id': 'invalid-share'})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context)


class RegenerateQuestionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.question = Question.objects.create(
            text="Original question",
            topic="Test",
            difficulty="Easy",
            question_type="short",
            marks=2
        )

    def test_regenerate_get_not_allowed(self):
        response = self.client.get(
            reverse('regenerate_question', kwargs={'question_id': self.question.id})
        )
        self.assertEqual(response.status_code, 405)

    def test_regenerate_invalid_question(self):
        response = self.client.post(
            reverse('regenerate_question', kwargs={'question_id': 99999})
        )
        self.assertEqual(response.status_code, 404)


class QuizFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.question1 = Question.objects.create(
            text="Q1", topic="Test", difficulty="Easy", question_type="short", marks=1
        )
        self.question2 = Question.objects.create(
            text="Q2", topic="Test", difficulty="Easy", question_type="short", marks=1
        )

    def test_start_quiz(self):
        self.client.login(username='testuser', password='testpass123')
        ids = f"{self.question1.id},{self.question2.id}"
        response = self.client.get(f"{reverse('start_quiz')}?ids={ids}")
        self.assertEqual(response.status_code, 200)

    def test_start_quiz_empty_ids(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('start_quiz'))
        self.assertEqual(response.status_code, 302)
