# 🎓 Qurio — AI-Powered Question Generator

An intelligent study platform that transforms your documents into question papers, flashcards, quizzes, and study notes using Google's Gemini AI.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📝 **Question Generator** | Generate MCQ, Short Answer, Long Answer, True/False, and Numerical questions from PDFs, DOCX, TXT, or pasted text |
| 🧠 **Interactive Quiz** | Take timed quizzes with auto-grading, progress tracking, and detailed results |
| 🃏 **Flashcard Generator** | Create interactive flashcards with 3D flip animations and shuffle mode |
| 🤖 **AI Answer Evaluator** | Submit your answers and get AI-powered feedback with scores, strengths, and suggestions |
| 📒 **Short Notes Generator** | Generate concise, organized study notes from your documents |
| 💡 **Topic Extraction** | Extract and understand key topics from your PDFs |
| 📊 **Analytics Dashboard** | Track your study progress with visual charts (difficulty, Bloom's taxonomy, question types) |
| 📄 **Export Options** | Download as professional PDF (exam-style) or Word document (DOCX) |
| 🔗 **Share Papers** | Generate shareable links for your question papers |
| 🔐 **User Authentication** | Sign up, log in, and manage your account |
| 🌗 **Dark/Light Theme** | Glass morphism UI with smooth theme switching |
| 🏷️ **Bloom's Taxonomy** | Every question tagged with cognitive level (Remember → Create) |

## 🛠️ Tech Stack

- **Backend:** Django 6.0
- **AI:** Google Gemini 2.5 Flash
- **PDF Generation:** ReportLab
- **Word Export:** python-docx
- **PDF Parsing:** PyPDF2
- **Frontend:** Bootstrap 5, Font Awesome, vanilla JS
- **Database:** SQLite (development)

## 🚀 Setup

### 1. Clone the repository
```bash
git clone https://github.com/saidinesh1801/qurio.git
cd qurio
```

### 2. Create a virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API key
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_google_gemini_api_key_here
```

Get a free API key at [Google AI Studio](https://aistudio.google.com/).

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Start the server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

## 📁 Project Structure

```
Question Generation App/
├── core/                    # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── generator/               # Main application
│   ├── models.py            # Question, QuizSession, Flashcard models
│   ├── views.py             # All view functions
│   ├── urls.py              # URL routing
│   ├── utils.py             # PDF/DOCX generation, text extraction
│   ├── tests.py             # Unit tests
│   ├── templates/           # HTML templates
│   │   ├── base.html        # Base template (shared CSS/JS)
│   │   ├── index.html       # Home page
│   │   ├── upload.html      # Question generator
│   │   ├── quiz.html        # Interactive quiz
│   │   ├── flashcards.html  # Flashcard viewer
│   │   ├── evaluator.html   # AI answer evaluator
│   │   ├── analytics.html   # Dashboard
│   │   ├── preview.html     # Question preview
│   │   ├── features.html    # Feature showcase
│   │   ├── history.html     # Question history
│   │   ├── login.html       # Login page
│   │   └── signup.html      # Registration page
│   └── static/              # Static assets (logo, images)
├── manage.py
├── requirements.txt
└── .env                     # API keys (not in repo)
```

## 🧪 Running Tests

```bash
python manage.py test generator
```

## 📋 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page |
| `/upload/` | GET, POST | Generate questions |
| `/preview/` | GET | Preview generated questions |
| `/quiz/` | GET | Start interactive quiz |
| `/flashcards/` | GET, POST | Generate flashcards |
| `/evaluate/<id>/` | GET, POST | AI answer evaluation |
| `/analytics/` | GET | Analytics dashboard |
| `/history/` | GET | Question history |
| `/short-notes/` | GET, POST | Generate short notes |
| `/pdf-topic-generator/` | GET, POST | Extract topics |
| `/login/` | GET, POST | User login |
| `/signup/` | GET, POST | User registration |

## 📝 License

MIT License — feel free to use this project for learning and personal use.
