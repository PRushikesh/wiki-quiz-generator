Wikipedia Quiz Generator (Full-Stack)

This project implements a full-stack solution to automatically generate multiple-choice quizzes from any provided Wikipedia article URL using a Large Language Model (LLM) via LangChain.

Technical Stack

Backend: Python 3.11+, FastAPI

Database: SQLModel (using SQLite locally, configurable for PostgreSQL/MySQL)

LLM: Gemini (via langchain-google-genai)

Scraping: Beautiful Soup 4 (bs4)

Frontend: HTML, JavaScript, Tailwind CSS (Single-File App)

1. Backend Setup and Running

Prerequisites

Python 3.11+

A Gemini API Key (set as an environment variable or in backend/quiz_generator.py).

Installation

# Clone the repository (simulated)
# git clone <repo_url>
# cd wikipedia-quiz-generator

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install dependencies
pip install fastapi uvicorn sqlmodel requests beautifulsoup4 pydantic python-dotenv
# For LLM functionality
pip install langchain langchain-google-genai


Configuration

Set your Gemini API key as an environment variable:

export GEMINI_API_KEY="YOUR_API_KEY_HERE"


Running the Server

Run the FastAPI application using Uvicorn:

uvicorn backend.main:app --reload


The API will be available at http://127.0.0.1:8000.

2. API Endpoints

Method

Endpoint

Description

GET

/

Health check.

POST

/generate_quiz

Generates a quiz from a URL, stores it, and returns details.

GET

/history

Returns a list of all quiz generation records.

GET

/quiz/{quiz_id}

Returns the full details of a specific quiz.

Example POST Request to /generate_quiz

{
  "input_url": "[https://en.wikipedia.org/wiki/Alan_Turing](https://en.wikipedia.org/wiki/Alan_Turing)"
}


3. LangChain Prompt Templates

The core LLM prompt is designed to ensure factual grounding and strict adherence to the required JSON structure using a Pydantic Output Parser.

Pydantic Schema (QuizOutputSchema in backend/quiz_generator.py)

This schema defines the mandatory JSON structure:

class QuizOutputSchema(BaseModel):
    quiz: List[QuizQuestionSchema] = Field(...) # 5-10 questions
    related_topics: List[str] = Field(...) # 3-5 topics
    key_entities: Dict[str, List[str]] = Field(...) # { 'people': [...], 'organizations': [...] }


System Prompt Template (QUIZ_PROMPT_TEMPLATE in backend/quiz_generator.py)

You are an expert educational content generator. Your task is to analyze the provided Wikipedia article text
and generate a comprehensive, factual quiz and relevant metadata.

**INSTRUCTIONS:**
1. Generate exactly 5 to 10 multiple-choice questions (MCQs).
2. Each question MUST have exactly four options (A, B, C, D).
3. The correct 'answer' field MUST match one of the option texts exactly.
4. The 'explanation' must be grounded ONLY in the provided article text.
5. Extract 3-5 key entities organized by categories like 'people', 'organizations', and 'locations'.
6. Suggest 3-5 'related_topics' for further reading based on the main subject.

**ARTICLE TEXT:**
---
{article_text}
---

**QUIZ TOPIC:** {title}
