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
                "content": "You are NMIT-GPT, an accurate and concise academic assistant. Answer questions using the provided context. 'Who takes', 'who teaches', 'who handles' all mean the same — find the faculty name from the context and return it. Never say information is not available if the context clearly contains the answer"
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )
    return response.choices[0].message.content
