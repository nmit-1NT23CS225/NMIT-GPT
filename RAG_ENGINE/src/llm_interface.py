from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama3-8b-8192"

def generate_llm_answer(prompt: str) -> str:
    """Generate the final answer using LLaMA-3 (Groq)."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are FacultyGPT, an academic assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
