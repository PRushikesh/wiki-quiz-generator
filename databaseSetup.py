import os
from datetime import datetime
from sqlmodel import SQLModel, create_engine, Field, Session, JSON
from typing import Optional, Dict, List, Any
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

# --- Database Configuration ---
# Use a default SQLite DB for simplicity in this example structure,
# but the user should configure for POSTGRESQL/MYSQL in a real deployment.
# Example for PostgreSQL: 'postgresql://user:password@host:port/dbname'
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./quiz_data.db")

# Create the engine, echo=True prints SQL queries (useful for debugging)
engine = create_engine(DATABASE_URL, echo=True)

# --- Database Model ---

class QuizData(SQLModel, table=True):
    """
    Database model to store the results of a single quiz generation.
    Complex JSON fields are stored as JSON strings in the database.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Core Metadata
    url: str = Field(index=True)
    title: str
    summary: str

    # Complex Data (Stored as JSON strings)
    # Using 'JSON' type from SQLAlchemy for better handling in modern DBs, 
    # but the API code (main.py) still uses json.dumps/loads for safe transfer.
    key_entities: str = Field(sa_column=Column(JSON))
    sections: str = Field(sa_column=Column(JSON))
    quiz: str = Field(sa_column=Column(JSON))
    related_topics: str = Field(sa_column=Column(JSON))
    
    # Timestamps
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), server_default=func.now()))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()))

    # For Pydantic model_dump/load to work with complex fields
    class Config:
        arbitrary_types_allowed = True


# --- Database Functions ---

def init_db():
    """Initializes the database by creating tables."""
    # If using SQLModel/SQLAlchemy with a different DB, 
    # you might need to adjust based on connection pooling/async requirements.
    SQLModel.metadata.create_all(engine)

def get_session():
    """Yields a new database session."""
    with Session(engine) as session:
        yield session
