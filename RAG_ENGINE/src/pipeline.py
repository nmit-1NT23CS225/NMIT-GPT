from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer

def build_prompt(user_query: str, chunks: list) -> str:
    """Format context and question into a prompt for LLaMA."""
    context = ""
    for c in chunks:
        context += f"- {c['content']}\n"

    prompt = f"""
Use the provided context to answer the question.
If the context does not contain the answer, respond:
"I am not able to find that information in the knowledge base."

[Context]
{context}

[Question]
{user_query}

[Answer]
"""
    return prompt.strip()

def answer_query(user_query: str, top_k: int = 5):
    """End-to-end RAG pipeline: embed → retrieve → prompt → LLM answer."""
    chunks = retrieve_top_chunks(user_query, top_k)
    prompt = build_prompt(user_query, chunks)
    answer = generate_llm_answer(prompt)

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": chunks
    }
