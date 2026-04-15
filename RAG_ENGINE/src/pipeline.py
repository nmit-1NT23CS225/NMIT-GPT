from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer
from .query_parser import parse_query
from .sql_queries import query_timetable, query_subjects
from .sql_queries import query_timetable, query_subjects, query_calendar,format_calendar_chunks


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
    #print("PARSED:", parsed)
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
    else:
        chunks = retrieve_top_chunks(user_query, top_k)

    if not chunks:
        return {
            "query": user_query,
            "answer": "No relevant information found in the knowledge base.",
            "chunks_used": [],
        }

    prompt = build_prompt(user_query, chunks)
    #print("PROMPT:", prompt)
    answer = generate_llm_answer(prompt)
    #print("ANSWER:", answer)

    answer = answer.replace("\n- ", ", ")
    answer = answer.replace("\n", " ")
    answer = " ".join(answer.split())

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": chunks,
    }