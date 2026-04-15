from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer
from .query_parser import parse_query
from .sql_queries import (
    query_timetable, query_subjects, query_calendar, query_faculty,
    format_calendar_chunks, format_faculty_chunks
)


def build_prompt(user_query: str, chunks: list) -> str:
    """Assemble context and question into a prompt for the LLM."""
    
    context_lines = []
    
    for c in chunks:
        content = c.get("content")
        metadata = c.get("metadata", {})
        name = metadata.get("name", "Unknown")

        if not content:
            continue

        context_lines.append(content)

    context = "\n\n".join(context_lines)
    
    # --- SAFETY NET FOR GROQ TOKEN LIMITS ---
    # 1 token is roughly 4 characters. 
    # To stay safely under Groq's 6,000 token limit, we cap the context at 15,000 characters.
    MAX_CHARS = 15000
    if len(context) > MAX_CHARS:
        context = context[:MAX_CHARS] + "\n...[Context Truncated for length]"
    # ----------------------------------------

    prompt = f"""
You are an intelligent academic assistant.

Answer the question ONLY using the provided context.

How to format your answer:
1. Specific Questions (e.g., "Who is the HOD?", "What is Dr. Smith's email?"): Give a very short, direct answer.
2. General Inquiries (e.g., "Tell me about the HOD of CSE"): Write a natural 2-3 sentence summary. Include their name, role, years of experience, and a brief mention of their interests or subjects taught. Do not list everything.
3. Detailed Requests (e.g., "Tell me everything about...", "Give in detail..."): Provide a comprehensive, well-formatted profile using bullet points for their experience, research, achievements, and subjects.

If the answer is not found in the context, say: "Information not available."

[Context]
{context}

[Question]
{user_query}

[Answer]
"""
    return prompt.strip()


def format_timetable_chunks(data: list) -> list:
    chunks = []
    for row in data:
        subject = row.get("subject_info") or {}
        faculty = subject.get("faculty_biodata") or {}

        text = (
            f"On {row.get('day_of_week')}, "
            f"class {row.get('class')} has "
            f"{subject.get('subject_name', 'unknown subject')} "
            f"during period {row.get('time_slot')}, "
            f"taught by {faculty.get('name', 'unknown faculty')}."
        )
        chunks.append({
            "content": text,
            "metadata": {"source_type": "timetable"},
            "similarity": 1.0
        })
    return chunks


def format_subject_chunks(data: list) -> list:
    chunks = []
    for row in data:
        faculty = row.get("faculty_biodata") or {}
        lab = row.get("lab_infrastructure") or {}

        text = (
            f"{row.get('subject_name')} (code: {row.get('subject_code')}) "
            f"is taught to class {row.get('class')} "
            f"by {faculty.get('name', 'unknown faculty')}."
        )
        if lab:
            text += f" Lab: {lab.get('lab_name')} in room {lab.get('room_number')}."

        chunks.append({
            "content": text,
            "metadata": {"source_type": "subjects"},
            "similarity": 1.0
        })
    return chunks


def answer_query(user_query: str, top_k: int = 5):
    parsed = parse_query(user_query)
    intent = parsed.get("intent", "general")

    if intent == "timetable":
        raw_data = query_timetable(parsed)
        chunks = format_timetable_chunks(raw_data)

    elif intent == "subjects":
        raw_data = query_subjects(parsed)
        chunks = format_subject_chunks(raw_data)

    elif intent == "calendar":
        raw_data = query_calendar(parsed)
        chunks = format_calendar_chunks(raw_data)

    elif intent == "faculty":
        raw_data = query_faculty(parsed)
        chunks = format_faculty_chunks(raw_data)

    else:
        # general/lab/anything else → vector search
        chunks = retrieve_top_chunks(user_query, top_k)

    if not chunks:
        return {
            "query": user_query,
            "answer": "No relevant information found in the knowledge base.",
            "chunks_used": [],
        }

    prompt = build_prompt(user_query, chunks)
    answer = generate_llm_answer(prompt)

    answer = answer.replace("\n- ", ", ")
    answer = answer.replace("\n", " ")
    answer = " ".join(answer.split())

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": chunks,
    }