import re
import json
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# LangChain Imports - Requires 'langchain', 'langchain-google-genai', 'pydantic'
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser

# --- LLM Configuration ---
# NOTE: Replace with your actual key or set it in your environment variables (GEMINI_API_KEY)
# Using a large model for better reasoning and structured output quality.
# This assumes the user will configure the key for the model specified.
LLM_MODEL = "gemini-2.5-pro"
LLM = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0.3)

# --- Pydantic Schemas for Structured LLM Output ---

class QuizQuestionSchema(BaseModel):
    question: str = Field(description="The question text.")
    options: List[str] = Field(description="A list of exactly four answer options (A-D).")
    answer: str = Field(description="The correct answer text, must exactly match one of the options.")
    difficulty: str = Field(description="Difficulty level, must be 'easy', 'medium', or 'hard'.")
    explanation: str = Field(description="A short explanation justifying the correct answer based on the article content.")

class QuizOutputSchema(BaseModel):
    quiz: List[QuizQuestionSchema] = Field(description="A list of 5 to 10 generated quiz questions.")
    related_topics: List[str] = Field(description="A list of 3-5 suggested Wikipedia topics for further reading.")
    key_entities: Dict[str, List[str]] = Field(description="Key entities extracted from the text, organized by type (e.g., 'people', 'organizations').")

# --- LangChain Prompts ---

# 1. Prompt for structured output generation
QUIZ_PROMPT_TEMPLATE = """
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
"""

def scrape_wikipedia_article(url: str) -> Dict[str, Any]:
    """Scrapes a Wikipedia URL and extracts key data."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Extract Title
        title_tag = soup.find('h1', {'id': 'firstHeading'})
        title = title_tag.text if title_tag else "Unknown Article Title"

        # 2. Extract Main Content/Summary (usually the first few paragraphs before the first h2)
        content_div = soup.find('div', {'id': 'mw-content-text'})
        paragraphs = content_div.find_all('p', recursive=False) if content_div else []
        
        # Clean up text from references [1], [2], etc.
        def clean_text(text):
            return re.sub(r'\[\d+\]', '', text).strip()

        raw_summary = ""
        for p in paragraphs:
            p_text = clean_text(p.text)
            if p_text:
                raw_summary += p_text + "\n"
            if len(raw_summary.split()) > 200: # Limit summary length for prompt token efficiency
                break
        
        summary = raw_summary.strip()
        
        # 3. Extract All Text for LLM (Focusing on the main body of the article)
        main_content_parts = []
        full_text = []
        
        # Find all section headers (h2)
        h2_sections = content_div.find_all('h2', recursive=False) if content_div else []
        
        # Get text from the top until the first 'See also' or 'References' section
        sections_list = []
        stop_titles = ["See also", "References", "External links", "Notes", "Further reading"]
        
        current_element = content_div.select_one('.mw-parser-output > *')
        while current_element:
            if current_element.name in ['h2', 'h3']:
                section_title = current_element.text.split('[')[0].strip()
                if section_title in stop_titles:
                    break
                sections_list.append(section_title)
            
            # Only add text from paragraphs, list items, and summary content
            if current_element.name in ['p', 'li'] or current_element.get('id') == 'firstHeading':
                full_text.append(clean_text(current_element.text))
            
            current_element = current_element.next_sibling
            
        full_article_text = "\n\n".join(full_text)

        if not full_article_text:
            raise ValueError("Could not extract meaningful content from the article.")

        return {
            "url": url,
            "title": title,
            "summary": summary,
            "full_article_text": full_article_text,
            "sections": sections_list
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch or parse URL: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {e}")

def generate_quiz_from_text(article_text: str, title: str) -> Dict[str, Any]:
    """Uses LLM to generate the structured quiz data."""
    try:
        # Define the Pydantic Output Parser
        parser = PydanticOutputParser(pydantic_object=QuizOutputSchema)

        # Construct the full prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", QUIZ_PROMPT_TEMPLATE),
            ("human", "Generate the quiz and metadata based on the text. Return the output in the required JSON format: {format_instructions}"),
        ]).partial(format_instructions=parser.get_format_instructions())

        # Prepare the input chain
        chain = prompt | LLM | parser

        # Invoke the chain
        llm_response = chain.invoke({
            "article_text": article_text,
            "title": title
        })
        
        # llm_response is a QuizOutputSchema object
        return llm_response.model_dump()

    except Exception as e:
        print(f"LLM generation failed: {e}")
        # The prompt is critical for grounding and structure, use a clear error message.
        raise HTTPException(status_code=500, detail=f"LLM Quiz Generation Failed. Check API key and token limits. Error: {e}")


def generate_quiz_from_url(url: str) -> Dict[str, Any]:
    """Orchestrates scraping and LLM generation."""
    # 1. Scrape the article
    scraped_data = scrape_wikipedia_article(url)

    # 2. Generate the quiz from the scraped text
    quiz_and_metadata = generate_quiz_from_text(
        article_text=scraped_data["full_article_text"],
        title=scraped_data["title"]
    )
    
    # 3. Combine all data into the final output structure
    final_output = {
        "url": scraped_data["url"],
        "title": scraped_data["title"],
        "summary": scraped_data["summary"],
        "sections": scraped_data["sections"],
        # Data from LLM response
        "quiz": quiz_and_metadata["quiz"],
        "related_topics": quiz_and_metadata["related_topics"],
        "key_entities": quiz_and_metadata["key_entities"]
    }
    
    return final_output
