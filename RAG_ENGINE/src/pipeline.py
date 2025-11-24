# pipeline.py

from .embedder import embed_query
from .retriever import search_similar
from .llm_interface import generate_answer


def answer_query(user_query: str, top_k: int = 5):
    """
    High-level RAG pipeline:
    1. Embed the query
    2. Vector search in DB
    3. LLM response using retrieved docs
    """
    print("[RAG] Embedding query ...")
    embedding = embed_query(user_query)

    if embedding is None:
        return "Error generating embedding!"

    print("[RAG] Searching vector DB ...")
    docs = search_similar(embedding, top_k)

    print(f"[RAG] Retrieved {len(docs)} relevant documents")

    print("[RAG] Generating answer ...")
    answer = generate_answer(user_query, docs)

    return answer

#remove this block once we import data from UI
if __name__ == "__main__":
    query = "What is machine learning?"
    result = answer_query(query)
    print("\nFinal Answer:\n", result)
