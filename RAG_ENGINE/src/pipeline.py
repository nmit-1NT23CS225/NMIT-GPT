from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer
from .query_parser import parse_query
from .sql_queries import (
    query_timetable, query_subjects, query_calendar, query_faculty,
    format_calendar_chunks, format_faculty_chunks,retrieve_chunks
)

def build_prompt(user_query: str, chunks: list, params: dict = None) -> str:
    context_lines = []
    for c in chunks:
        content = c.get("content")
        if not content:
            continue
        context_lines.append(content)

    # if no chunks, tell LLM the calendar has no entry for that date
    if not context_lines and params and params.get("date"):
        context_lines.append(f"The academic calendar has no recorded events for {params['date']}.")

    context = "\n\n".join(context_lines)

    # --- SAFETY NET FOR GROQ TOKEN LIMITS ---
    MAX_CHARS = 15000
    if len(context) > MAX_CHARS:
        context = context[:MAX_CHARS] + "\n...[Context Truncated for length]"
    # ----------------------------------------

    prompt = f"""
You are an intelligent academic assistant for NMIT college students.

Use the context below to answer the student's question.

How to format your answer for Faculty queries:
1. Specific Questions (e.g., "Who is the HOD?", "What is Dr. Smith's email?"): Give a very short, direct answer.
2. General Inquiries (e.g., "Tell me about the HOD of CSE"): Write a natural 2-3 sentence summary. Include their name, role, years of experience, and a brief mention of their interests or subjects taught. Do not list everything.
3. Detailed Requests (e.g., "Tell me everything about...", "Give in detail..."): Provide a comprehensive, well-formatted profile using bullet points for their experience, research, achievements, and subjects.
4. Count Queries (e.g., "How many assistant professors?", "How many professors?", "How many HODs?"): Count ONLY the entries explicitly present in the context. Do NOT guess, assume, or add extras. The answer must match exactly the number of entries in the context.
5. List Queries (e.g., "List all teachers", "List all associate professors"): List ONLY the names explicitly present in the context. Do NOT add any names that are not in the context. Do NOT repeat the same name twice.
Rules for Calendar queries:
-"college fest"-> Anaadyantha
-"start of sem"->Commencement of classes
- Read the context carefully and reason from it
- "when does X start" → find the earliest date for X
- "when does X end" → find the latest date for X
- "when is X" → give the full date range
- If the calendar has no events for a date → college is open as usual on that day
- If it is a holiday → college is CLOSED
- If it is a compensatory working day → college is OPEN
- Convert YYYY-MM-DD dates to readable format like "May 13, 2026"
- If multiple events match, list all of them
- Be concise and direct
- Dates are in YYYY-MM-DD format where MM is month and DD is day
- 2026-02-06 means February 6, 2026 (month=02=February, day=06)
- 2026-06-12 means June 12, 2026 (month=06=June, day=12)
- Never swap month and day
- Any question asking "when does sem/semester/classes start" OR "when does sem [number] start" 
  → This is asking for the date of 'Commencement of Classes'. 
  → Find 'Commencement of Classes' in the context and return its date.
  → Example answer: "January 19, 2026"
- NEVER say "Information not available" if the context contains 'Commencement of Classes' 
  and the question is about when semester/classes start.
- Give only the direct answer, no assumptions, no extra sentences
- Do not mention what might happen next or what other events might exist
- List ALL events from the context, do not skip any
- "X Ends" means the end date of event X — use that date as the answer for "when does X end"
- "X Starts" means the start date of event X — use that date as the answer for "when does X start"
- "Give the dates according to the date given in the context"
- For count queries: count ONLY the entries explicitly present in the context, do NOT guess or add extras
- NEVER include names not present in the context
- "when does X end" → give ONLY the end date, nothing else
  Example: "July 3, 2026"
- "when does X start" → give ONLY the start date
  Example: "June 12, 2026"
- "when is X" → give the full date range
  Example: "June 12, 2026 to July 3, 2026"
- Never repeat the date twice in the same answer
CRITICAL — NEVER DO YOUR OWN DATE MATH:
- The context chunks already contain the EXACT pre-calculated answer from the database.
- For gap queries: use the number from the chunk "The gap between X and Y is N working days."
- For duration queries: use the number from the chunk "X spans N days."
- NEVER subtract dates yourself. Raw date subtraction ignores Sundays, holidays, and
  co-curricular days — it will always produce a wrong answer.
- If the context says the gap is 40 days, your answer is exactly 40. Do not recompute.
- If the context says an event spans 10 days, your answer is exactly 10. Do not recompute.
- "number of days from X to Y" = gap (working days between them) — use the gap chunk value.
- "how many days is X" = duration (days of the event itself) — use the duration chunk value.
TEACHING DAYS = WORKING DAYS:
- "working days", "teaching days", "class days", "college days" all mean the SAME thing.
- If the context contains "There are X teaching days" → the answer is simply "X teaching days/working days".
- NEVER calculate or subtract anything. NEVER say "let me calculate".
- NEVER mention holidays, Sundays, or date ranges in the answer.
- Just return the number directly.
  Example: "There are 78 working days this semester."
STRICT RULES (VERY IMPORTANT):
- You MUST answer ONLY using the provided context.
- NEVER use prior knowledge or assumptions.
- NEVER guess missing dates or values.
- If ANY required data is missing → respond EXACTLY:
  "Information not available."
- DO NOT attempt partial calculations if data is incomplete.
- Never say "Information not available" if the context has any event data
- "fest" specifically refers to the college cultural fest "Anaadyanta" only
- co_curricular events are separate activities, not the fest
- Only call something a fest if event_name is "Anaadyanta"

**Rules for Timetable queries:
- When showing a full day timetable, list ALL periods in time order
- Format each period as: "Period <time>: <subject> by <faculty>"
- Never skip any period
- If asked for a specific day, only show that day's periods
- Present as a numbered list when showing full day schedule




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

    # sort by time slot so periods are in order
    def time_sort_key(row):
        slot = row.get("time_slot", "")
        return slot  # "09:00-09:55" sorts correctly as string

    sorted_data = sorted(data, key=time_sort_key)

    for row in sorted_data:
        subject = row.get("subject_info") or {}
        faculty = subject.get("faculty_biodata") or {}

        subject_name = subject.get("subject_name")
        faculty_name = faculty.get("name")

        # skip completely unknown rows
        if not subject_name and not faculty_name:
            continue

        text = (
            f"Period {row.get('time_slot')}: "
            f"{subject_name or 'unknown subject'} "
            f"taught by {faculty_name or 'unknown faculty'} "
            f"(Day: {row.get('day_of_week')}, Class: {row.get('class')})."
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
def answer_query(user_query: str, top_k: int = 5, chat_history: list = None) -> dict:
    parsed = parse_query(user_query, chat_history=chat_history) 
    print("PARSED:", parsed)
    intent = parsed.get("intent", "general")

    if intent == "timetable":
        cls = parsed.get("class")
    
    # only number given e.g. "6" → ask which section
        if cls and cls.isdigit():
            return {
                "query": user_query,
                "answer": f"Which section of {cls}? For example: {cls}A, {cls}B, {cls}C, or {cls}D?",
                "chunks_used": []
        }
    
    # only letter given e.g. "D" or "d section" → ask which semester
        if cls and cls.isalpha() and len(cls) == 1:
            return {
                "query": user_query,
                "answer": f"Which semester is section {cls.upper()}? For example: 4{cls.upper()}, 5{cls.upper()}, or 6{cls.upper()}?",
                "chunks_used": []
        }

    # resolve tomorrow/date to day name
        if parsed.get("date") and not parsed.get("day"):
            from datetime import datetime
            try:
                dt = datetime.strptime(parsed["date"], "%Y-%m-%d")
                parsed["day"] = dt.strftime("%A")
                print("RESOLVED DAY FROM DATE:", parsed["day"])
            except:
                pass

        raw_data = query_timetable(parsed)
        chunks = format_timetable_chunks(raw_data)

    elif intent == "subjects":
        raw_data = query_subjects(parsed)
        chunks = format_subject_chunks(raw_data)

    elif intent == "calendar":
        chunks=retrieve_chunks(parsed)
        
    elif intent == "faculty":
        print("PARAMS SENT TO QUERY_FACULTY:", parsed)
        raw_data = query_faculty(parsed)
        is_list_query = parsed.get("is_list_query", False)  # 👈 from parser
        chunks = format_faculty_chunks(raw_data, compact=is_list_query)
    

    else:
        chunks = retrieve_top_chunks(user_query, top_k)

    # only return early for non-calendar intents
    if not chunks and intent != "calendar":
        return {
            "query": user_query,
            "answer": "No relevant information found in the knowledge base.",
            "chunks_used": [],
        }
    print("CHUNKS COUNT:", len(chunks))
    prompt = build_prompt(user_query, chunks, params=parsed)  # pass parsed here
    #print("PROMPT:", prompt)
    answer = generate_llm_answer(prompt, chat_history=chat_history)

    answer = answer.replace("\n- ", ", ")
    answer = answer.replace("\n", " ")
    answer = " ".join(answer.split())

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": chunks,
    }