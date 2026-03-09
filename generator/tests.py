from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from generator.models import Question, QuizSession, FlashcardSet, Flashcard


class QuestionModelTest(TestCase):
    def test_create_question(self):
        q = Question.objects.create(
            text="What is Python?", answer="A programming language",
            topic="Programming", difficulty="Easy", marks=2,
            question_type="short", bloom_level="remember",
        )
        self.assertEqual(str(q), "Programming (Easy) - 2 Marks")
        self.assertIsNotNone(q.created_at)
        self.assertEqual(q.bloom_level, "remember")

    def test_question_ordering(self):
        q1 = Question.objects.create(text="Q1", topic="T", difficulty="Easy", marks=1)
        q2 = Question.objects.create(text="Q2", topic="T", difficulty="Easy", marks=1)
        questions = list(Question.objects.all())
        self.assertEqual(questions[0], q2)  # newest first


class QuizSessionModelTest(TestCase):
    def test_create_quiz_session(self):
        session = QuizSession.objects.create(topic="Physics", total=10)
        self.assertFalse(session.completed)
        self.assertIsNotNone(session.session_id)

    def test_quiz_with_questions(self):
        q1 = Question.objects.create(text="Q1", topic="T", difficulty="Easy", marks=1)
        q2 = Question.objects.create(text="Q2", topic="T", difficulty="Easy", marks=2)
        session = QuizSession.objects.create(topic="T", total=2)
        session.questions.set([q1, q2])
        self.assertEqual(session.questions.count(), 2)


class FlashcardModelTest(TestCase):
    def test_create_flashcard_set(self):
        fc_set = FlashcardSet.objects.create(topic="Biology")
        card = Flashcard.objects.create(
            flashcard_set=fc_set, front="What is DNA?",
            back="Deoxyribonucleic acid", order=0,
        )
        self.assertEqual(fc_set.cards.count(), 1)
        self.assertIn("What is DNA", str(card))


class PageLoadTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_page(self):
        r = self.client.get(reverse('index'))
        self.assertEqual(r.status_code, 200)

    def test_features_page(self):
        r = self.client.get(reverse('features'))
        self.assertEqual(r.status_code, 200)

    def test_upload_page(self):
        r = self.client.get(reverse('upload'))
        self.assertEqual(r.status_code, 200)

    def test_history_page(self):
        r = self.client.get(reverse('history'))
        self.assertEqual(r.status_code, 200)

    def test_analytics_page(self):
        r = self.client.get(reverse('analytics'))
        self.assertEqual(r.status_code, 200)

    def test_flashcards_page(self):
        r = self.client.get(reverse('flashcards'))
        self.assertEqual(r.status_code, 200)

    def test_short_notes_page(self):
        r = self.client.get(reverse('short_notes'))
        self.assertEqual(r.status_code, 200)

    def test_pdf_topic_generator_page(self):
        r = self.client.get(reverse('pdf_topic_generator'))
        self.assertEqual(r.status_code, 200)


class DeleteQuestionTest(TestCase):
    def test_delete_question(self):
        q = Question.objects.create(
            text="Test?", answer="Yes", topic="Test", difficulty="Easy", marks=1,
        )
        r = self.client.post(reverse('delete_question', args=[q.id]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Question.objects.filter(id=q.id).exists())

    def test_delete_nonexistent_returns_404(self):
        r = self.client.post(reverse('delete_question', args=[99999]))
        self.assertEqual(r.status_code, 404)


class AuthTests(TestCase):
    def test_login_page_loads(self):
        r = self.client.get(reverse('login'))
        self.assertEqual(r.status_code, 200)

    def test_signup_page_loads(self):
        r = self.client.get(reverse('signup'))
        self.assertEqual(r.status_code, 200)

    def test_signup_and_login(self):
        r = self.client.post(reverse('signup'), {
            'username': 'testuser', 'password1': 'Str0ngP@ss!', 'password2': 'Str0ngP@ss!',
        })
        self.assertEqual(r.status_code, 302)  # redirect on success
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_logout(self):
        User.objects.create_user('testuser', password='pass123')
        self.client.login(username='testuser', password='pass123')
        r = self.client.get(reverse('logout'))
        self.assertEqual(r.status_code, 302)
