from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()


MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in environment variables")

client = Groq(api_key=GROQ_API_KEY)


def generate_llm_answer(prompt: str) -> str:
    """Generate the final answer using the configured LLaMA model on Groq."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """You are NMIT-GPT, an academic assistant for students of NMIT college.
                Your job is to answer questions about timetables, subjects, faculty, exams, and college calendar.
                Always reason carefully from the provided context.
                Convert YYYY-MM-DD dates to readable format like 'May 13, 2026'.
                'Who takes', 'who teaches', 'who handles' all mean the same — find the faculty name from the context and return it.
                Never refuse to answer if the context contains relevant information.
                Be concise and direct."""
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )
    return response.choices[0].message.content
