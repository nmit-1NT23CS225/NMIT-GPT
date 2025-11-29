from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer


def build_prompt(user_query: str, chunks: list) -> str:
    """Assemble context and question into a prompt for the LLM."""
    context_lines = []
    for c in chunks:
        content = c.get("content")
        if not content:
            continue
        context_lines.append(f"- {content}")

    context = "\n".join(context_lines)

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

    # Fallback: no relevant chunks found
    if not chunks:
        return {
            "query": user_query,
            "answer": "No relevant information found in the knowledge base.",
            "chunks_used": [],
        }

    prompt = build_prompt(user_query, chunks)
    answer = generate_llm_answer(prompt)

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": chunks,
    }
