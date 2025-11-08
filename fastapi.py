import uvicorn
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List

from .database import init_db, get_session, QuizData
from .quiz_generator import generate_quiz_from_url

# --- Pydantic Schemas for API ---

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer: str
    difficulty: str
    explanation: str

class QuizOutput(BaseModel):
    url: HttpUrl
    title: str
    summary: str
    key_entities: dict
    sections: List[str]
    quiz: List[QuizQuestion]
    related_topics: List[str]

class QuizHistoryItem(BaseModel):
    id: int
    url: str
    title: str
    created_at: str

class QuizDetailResponse(QuizOutput):
    id: int
    created_at: str

# --- Application Setup ---

# Define the lifespan for initialization (e.g., database)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database tables
    print("Initializing Database...")
    init_db()
    yield
    # Shutdown: Clean up resources if necessary (not needed for simple SQLModel setup)
    print("Application shutdown complete.")

app = FastAPI(
    title="Wikipedia Quiz Generator API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS to allow the frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---

@app.get("/", tags=["Status"])
def read_root():
    """API health check."""
    return {"message": "Wikipedia Quiz Generator API is running!"}

@app.post("/generate_quiz", response_model=QuizDetailResponse, tags=["Quiz Generation"])
async def generate_and_store_quiz(input_url: HttpUrl):
    """
    Accepts a Wikipedia URL, scrapes the content, generates a quiz using LLM,
    stores the data, and returns the result.
    """
    try:
        # 1. Generate Quiz Data
        print(f"Processing URL: {input_url}")
        # Note: generate_quiz_from_url handles the scraping and LLM call
        quiz_data_dict = generate_quiz_from_url(str(input_url))

        # 2. Store Data in DB
        with get_session() as session:
            # Convert complex fields to JSON strings for storage
            db_item = QuizData(
                url=quiz_data_dict["url"],
                title=quiz_data_dict["title"],
                summary=quiz_data_dict["summary"],
                key_entities=json.dumps(quiz_data_dict["key_entities"]),
                sections=json.dumps(quiz_data_dict["sections"]),
                quiz=json.dumps(quiz_data_dict["quiz"]),
                related_topics=json.dumps(quiz_data_dict["related_topics"])
            )
            session.add(db_item)
            session.commit()
            session.refresh(db_item)

            # 3. Prepare Response (re-parse JSON strings back into dictionaries/lists)
            response_data = db_item.model_dump()
            response_data['key_entities'] = json.loads(db_item.key_entities)
            response_data['sections'] = json.loads(db_item.sections)
            response_data['quiz'] = json.loads(db_item.quiz)
            response_data['related_topics'] = json.loads(db_item.related_topics)
            response_data['created_at'] = db_item.created_at.isoformat()

            return QuizDetailResponse(**response_data)

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process URL: {str(e)}")


@app.get("/history", response_model=List[QuizHistoryItem], tags=["History"])
def get_quiz_history():
    """Retrieves a list of all previously generated quizzes."""
    with get_session() as session:
        # Select id, url, title, and created_at for the history list
        history_items = session.query(
            QuizData.id,
            QuizData.url,
            QuizData.title,
            QuizData.created_at
        ).all()

        return [
            QuizHistoryItem(
                id=item.id,
                url=item.url,
                title=item.title,
                created_at=item.created_at.isoformat()
            )
            for item in history_items
        ]

@app.get("/quiz/{quiz_id}", response_model=QuizDetailResponse, tags=["History"])
def get_quiz_details(quiz_id: int):
    """Retrieves the full details of a single quiz by ID."""
    with get_session() as session:
        db_item = session.get(QuizData, quiz_id)
        if not db_item:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Prepare Response (re-parse JSON strings back into dictionaries/lists)
        response_data = db_item.model_dump()
        response_data['key_entities'] = json.loads(db_item.key_entities)
        response_data['sections'] = json.loads(db_item.sections)
        response_data['quiz'] = json.loads(db_item.quiz)
        response_data['related_topics'] = json.loads(db_item.related_topics)
        response_data['created_at'] = db_item.created_at.isoformat()

        return QuizDetailResponse(**response_data)

if __name__ == "__main__":
    # To run: uvicorn main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
