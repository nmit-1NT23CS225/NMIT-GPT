# llm_interface.py
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

LLM_MODEL = "gpt-4o-mini"   # Fast & cheap, works well for RAG


def format_context(docs: list):
    """Combine all retrieved docs into a single context string"""
    context = ""
    for d in docs:
        context += f"\n- {d['content']}"
    return context.strip()


def generate_answer(user_query: str, retrieved_docs: list):
    """RAG: Send context + query to LLM and get answer"""
    context = format_context(retrieved_docs)

    prompt = f"""
You are Faculty GPT, an AI assistant trained on faculty materials.

Use ONLY the information from the context below to answer the user query.
If the context does not contain the answer, say:
"I'm not able to find that information in the knowledge base."

Context:
{context}

User Query:
{user_query}

Answer:
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful and accurate academic assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content
