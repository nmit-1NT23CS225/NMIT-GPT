from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer


def build_prompt(user_query: str, chunks: list) -> str:
    """Assemble context and question into a prompt for the LLM."""
    
    context_lines = []
    
    for c in chunks:
        content = c.get("content")
        metadata = c.get("metadata", {})
        name = metadata.get("name", "Unknown")

        if not content:
            continue

        context_lines.append(
            f"Faculty: {name}\nSubjects: {content}"
        )

    context = "\n\n".join(context_lines)
    prompt = f"""
You are an academic assistant.

Answer the question ONLY using the provided context.

Instructions:
- Give a clear and concise answer
- Do NOT explain your reasoning
- Do NOT list unrelated information
- Extract only relevant names or facts
- If multiple people match, list them clearly
- If answer is not found, say: "Information not available"

[Context]
{context}

[Question]
{user_query}

[Answer]
"""
    return prompt.strip()


def answer_query(user_query: str, top_k: int = 5):
    """End-to-end RAG pipeline: embed → retrieve → filter → prompt → LLM answer."""
    
    chunks = retrieve_top_chunks(user_query, top_k)

    # Fallback: no relevant chunks found
    if not chunks:
        return {
            "query": user_query,
            "answer": "No relevant information found in the knowledge base.",
            "chunks_used": [],
        }

    # STEP 1: extract keywords (remove useless words)
    stopwords = {"who", "teaches", "what", "is", "the", "does", "of", "in"}

    keywords = [
        word for word in user_query.lower().split()
        if word not in stopwords
    ]

    # STEP 2: filter chunks
    filtered_chunks = [
        c for c in chunks
        if any(k in c.get("content", "").lower() for k in keywords)
    ]

    # STEP 3: fallback if filtering removes everything
    final_chunks = filtered_chunks if filtered_chunks else chunks

    # STEP 4: build prompt
    prompt = build_prompt(user_query, final_chunks)

    answer = generate_llm_answer(prompt)

    # STEP 5: clean formatting
    answer = answer.replace("\n- ", ", ")
    answer = answer.replace("\n", " ")
    answer = " ".join(answer.split())

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": final_chunks,  # 👈 important change
    }
