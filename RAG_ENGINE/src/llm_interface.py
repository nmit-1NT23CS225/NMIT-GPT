from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()


MODEL = os.getenv("GROQ_LLM_MODEL", "llama3-8b-8192")
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
                "content": "You are FacultyGPT, an accurate and concise academic assistant."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )
    return response.choices[0].message.content
