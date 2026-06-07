from .retriever import retrieve_top_chunks
from .llm_interface import generate_llm_answer
from .query_parser import parse_query
from .sql_queries import (
    query_timetable, query_subjects, query_calendar, query_faculty,
    format_calendar_chunks, format_faculty_chunks,retrieve_chunks, query_lab, format_lab_chunks, query_lab_embeddings, query_lab_availability, query_lab_by_keyword, get_faculty_direct_field,query_class_teacher
)
# at top of pipeline.py
import re
import time
from datetime import datetime, timedelta
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
2. General Inquiries (e.g., "Tell me about the HOD of CSE"):
   Write a natural 2-3 sentence summary using ONLY their full name (never initials or short forms).
   The summary MUST naturally weave in:
     - Their full name and designation
     - Years of experience
     - Education
     - Areas of interest
     - Subjects they teach
     - Their email address
   Do not use bullet points or lists. Do not mention or use any short name, initials, or abbreviations for the faculty member.
3. Detailed Requests (e.g., "Tell me everything about...", "Give in detail..."): Provide a comprehensive, well-formatted profile using bullet points for their experience, research, achievements, and subjects.
4. Count Queries (e.g., "How many assistant professors?", "How many professors?", "How many HODs?"): Count ONLY the entries explicitly present in the context. Do NOT guess, assume, or add extras. The answer must match exactly the number of entries in the context.
5. List Queries (e.g., "List all teachers", "List all associate professors"): List ONLY the names explicitly present in the context. Do NOT add any names that are not in the context. Do NOT repeat the same name twice.
- NEVER say a faculty is HOD unless their designation explicitly contains "Head" or "HOD" in the context
- NEVER infer or assume a designation — only use what is explicitly stated in the context
- If designation says "Professor of Practice", say exactly that, not HOD, not Professor

FACULTY NAME RULES:
- Never use gendered pronouns (he, she, him, her, his, hers).
- Never infer gender from a name.
- After the first mention, continue using the faculty member's first name instead of pronouns.
- Example:
  Correct: "Dr. Vijaya Shetty has 32 years of experience. Vijaya's areas of interest include Data Mining."
  Correct: "Dr. Vijaya Shetty teaches Data Structures. Vijaya can be contacted at ..."
  Wrong: "He teaches ..."
  Wrong: "She teaches ..."
  Use:
  Vijaya's areas of interest...
  Vijaya's experience...
  Vijaya teaches...
  Never:
  His areas...
  Her areas...
 

Rules for Calendar queries:
-"college fest"-> Anaadyantha
-"start of sem"->Commencement of classes
- Read the context carefully and reason from it
- "when does X start" → find the earliest date for X
- "when does X end" → find the latest date for X
- "when is X" → give the full date range
- If the calendar has no events for a date → college is open as usual on that day
- If context contains an event that "starts on X and ends on Y" and today's date falls between X and Y → that event IS happening today, mention it explicitly
- If an exam event is ongoing today → say "SEE Practicals / SEE Theory / MSE is ongoing today (X to Y)" — NEVER say "open as usual" if an exam is ongoing
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
**CRITICAL — EXAM OVERRIDE RULE:
- BEFORE answering any timetable query, check if any calendar context chunk mentions an ongoing exam (SEE, MSE, Practicals).
- If an exam is ongoing on the queried date → respond ONLY with:
  "No classes on [date] — [Exam Name] is ongoing ([start date] to [end date])."
- NEVER list periods or subjects if an exam is ongoing. Exams override the timetable completely.
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
- ALWAYS convert dates from YYYY-MM-DD to readable format: "2026-05-13" → "May 13, 2026"
- NEVER show dates in YYYY-MM-DD format in your answer
TEACHING DAYS = WORKING DAYS:
- For college open/working day queries: answer in ONE sentence only. "Yes, May 13 is a normal working day." or "No, May 13 is a holiday — [name]."
- If query is ambiguous like "what do we have tomorrow", treat it as a calendar query and check for any events on that date
- "what do we have on X", "what's on X", "anything on X" → intent: "calendar", date: X

- "working days", "teaching days", "class days", "college days" all mean the SAME thing.
- If the context contains "There are X teaching days" → the answer is simply "X teaching days/working days".
- NEVER calculate or subtract anything. NEVER say "let me calculate".
- NEVER mention holidays, Sundays, or date ranges in the answer.
- Just return the number directly.
  Example: "There are 78 working days this semester."

Rules for Lab queries:
- ALWAYS answer from the context for lab queries — NEVER say "Information not available" if chunks are present
- "configuration" → report Processor, Speed, RAM, HDD
- "brands" → report system brands and counts  
- "details" or "tell me about" → combine: room number, total computers, brands, and full configuration
- The metadata field "lab_name" tells you which lab the chunk belongs to — use it
- For lab availability queries (is lab X free/occupied):
  ONLY output one sentence. No explanation, no time ranges, no reasoning.
  If OCCUPIED: "No, [lab name] is not free on [day] at [time]. It is occupied by class [class] for [subject]."
  If FREE: "Yes, [lab name] is free on [day] at [time]."
  If asking "is it occupied": 
    IF OCCUPIED: "Yes, [lab name] is occupied on [day] at [time] by class [class] for [subject]."
    IF FREE:  "No, [lab name] is not occupied on [day] at [time]."
  NEVER explain why. NEVER mention time ranges like 02:25-03:20. NEVER say "based on context". NEVER say "Information not available" if the context has OCCUPIED or FREE.
- Always mention the lab name in your answer
- For lab list queries: list ALL labs present in the context, do not skip any.NEVER omit any lab from the context. Count the chunks and list every single one.
- For lab hardware/spec queries: ALWAYS mention the lab name first in your answer. Format: "[Lab Name]: [details]" for each lab.
- For multiple lab availability queries: give one combined answer.
  Example: "No, both Computer Lab-3 and Computer Lab-4 are occupied on Wednesday at 11 AM by class 6D for Placement Practice Lab."
  If one is free and one is not: state each separately in one sentence each.
  NEVER say "Yes" and "No" for the same query. NEVER contradict yourself.
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

Rules for Timetable queries:
- "schedule of 6A on Monday" → list ALL periods in time order with subject and faculty
- "free periods for 6A on Wednesday" → list only the FREE time slots
- "what does Dr. X teach" → list all classes and time slots for that faculty
- "when is DBMS" → list every day + time slot where that subject appears
- "what is happening on Friday 3rd period" → list ALL classes with their subjects
- Always include the time slot (e.g. "09:00-09:55") AND the period number when available
- For lab sessions: say "Lab session" not "Lecture"
- For free-period answers: count them first, then list them
    Example: "Class 6A has 2 free periods on Wednesday: Period 4 (12:35-01:30), Period 7 (03:20-04:15)."
- NEVER say "Information not available" if chunks contain timetable rows
- If no rows found, say "No timetable entry found for [class] on [day]."
- CRITICAL: The context contains lines like "during Period X (time slot: HH:MM-HH:MM)"
- Copy the period number and time slot EXACTLY as written in the context — do NOT change them
- NEVER write a time slot that is not present in the context
- NEVER invent or approximate times like "10:25-11:20" or "11:20-12:15" — these do not exist
- Valid time slots are ONLY: 09:00-09:55, 10:05-11:00, 11:00-11:55, 12:35-01:30, 01:30-02:25, 02:25-03:20, 03:20-04:15
- If a time slot in your answer is not in the above list, you are hallucinating — stop and use the context value


-For count queries: the answer is simply the NUMBER of entries in context. Just say "There are X assistant professors." Nothing else.



Rules for Subject queries:
- "how many subjects" with no specific class → count the total number of UNIQUE subject names in the context
- NEVER count per class or per section — count unique subject names only once 
- ALWAYS count your listed items before writing the number
- The answer should be the count first, then list all unique subject names
- Example: "There are 12 subjects in 6th semester: 1. Operating System concepts 2. Cryptography and Network Security ..."
- "how many subjects" or "list all subjects" → count the items in your own answer list and report that number
- NEVER state a count number yourself — always count your listed items and use that number
- The count must ALWAYS match the number of items in your list
- Before writing "There are X subjects", count the items in your list first and then write the count
- Do not group by class when answering count queries about subjects
- "what subjects does X teach" or "which subjects does X take" → list ALL subject names present in the context, do NOT filter or skip any
- The context already contains ONLY the subjects taught by that faculty — trust the context completely, list everything in it
- NEVER say a subject is not taught by the faculty if it appears in the context
- "what subjects does X teach" → list ALL subject names in context, trust context completely, never skip any
- "Is the same faculty teaching X?" → if all chunks show same faculty name → "Yes, [name] teaches [subject] for all classes", if different → "No" and list each class with faculty
- "who teaches X for 6A and 6B" → list faculty for each class separately
- Example: "Dr. X teaches CNS for 6A, Dr. Y teaches CNS for 6B"
- "does X teach any lab?" → scan each chunk's subject name for the word "Lab" — if NONE contain "Lab" → answer "No, [faculty name] does not teach any lab subject" — NEVER say Yes unless a chunk explicitly has "Lab" in the subject name
- When the user asks for a "lab number" or "which lab", extract the Lab name and room number from the chunk, NOT the subject code.
- Example: "Lab: Computer Lab-1 (Room 120) in room 120" → answer "Computer Lab-1 in room 120"

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

    def time_sort_key(row):
        return row.get("time_slot", "")

    sorted_data = sorted(data, key=time_sort_key)

    for row in sorted_data:
        subject = row.get("subject_info") or {}
        faculty = subject.get("faculty_biodata") or {}
        is_lab = row.get("is_lab", False)

        subject_name = (
            subject.get("subject_name")
            or row.get("subject_code")
        )
        faculty_name = faculty.get("name")

        if not subject_name and not faculty_name:
            continue

        session_type = "Lab session" if is_lab else "Lecture"

        text = (
            f"Period {row.get('time_slot')} ({session_type}): "
            f"{subject_name or 'unknown subject'} "
            f"(Day: {row.get('day_of_week')}, Class: {row.get('class')})."
        )

        if not is_lab and faculty_name:
            text = text.rstrip(".") + f", taught by {faculty_name}."

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


# ── Period / day names used throughout ────────────────────────────────────────
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_SLOT_TO_PERIOD = {
    "09:00-09:55": "1", "10:05-11:00": "2", "11:00-11:55": "3",
    "12:35-01:30": "4", "01:30-02:25": "5", "02:25-03:20": "6", "03:20-04:15": "7",
}
# College sessions split by time (used for "morning" / "afternoon")
_MORNING_PERIODS   = ["1", "2", "3"]       # 09:00 – 11:55
_AFTERNOON_PERIODS = ["4", "5", "6", "7"]  # 12:35 – 04:15


def _day_name(dt) -> str:
    return _DAYS[dt.weekday()]


def _date_str(dt) -> str:
    return dt.strftime("%Y-%m-%d")


def _resolve_current_period() -> tuple:
    """Return (day_name, period_str, time_slot_str) for right now."""
    from .sql_queries import resolve_time_slot
    now = datetime.now()
    time_slot = resolve_time_slot(now.strftime("%H:%M"))
    if not time_slot:
        return _day_name(now), None, None
    return _day_name(now), _SLOT_TO_PERIOD.get(time_slot), time_slot


def _inject_temporal_context(query: str) -> str:
    """
    Pre-resolve every relative date/time word into an explicit date or
    period number before the LLM parser sees the query.

    Handled phrases (case-insensitive):
      now / currently / right now / ongoing / current period / current class
      morning / this morning
      afternoon / this afternoon
      today
      yesterday
      day before yesterday
      tomorrow / next day
      day after tomorrow
      this week  →  date_from … date_to

    For calendar queries the injection is a date string.
    For timetable queries with a time-of-day word the injection is a
    period number so the parser never has to do arithmetic.
    """
    from .sql_queries import resolve_time_slot
    q = query          # we will augment this string
    ql = query.lower()
    now = datetime.now()
    today     = now.date()

    def _fmt(d) -> str:          # date → "YYYY-MM-DD"
        return d.strftime("%Y-%m-%d")

    def _dname(d) -> str:        # date → "Monday" …
        return _DAYS[d.weekday()]

    # ── 1. now / currently / right now ────────────────────────────────────────
    NOW_WORDS = ["now", "current period", "currently", "ongoing", "right now", "current class"]
    if any(w in ql for w in NOW_WORDS):
        day, period, slot = _resolve_current_period()
        if period:
            q += (f" (current day is {day}, current period is {period},"
                  f" current time slot is {slot})")
        else:
            q += f" (current day is {day}, no class in progress)"
        return q          # handled — return early

    # ── 2. morning / afternoon ─────────────────────────────────────────────────
    if "this morning" in ql or (ql.count("morning") > 0 and "yesterday" not in ql and "tomorrow" not in ql):
        periods = ", ".join(_MORNING_PERIODS)
        q += f" (current day is {_dname(today)}, morning = periods {periods})"
        return q

    if "this afternoon" in ql or (ql.count("afternoon") > 0 and "yesterday" not in ql and "tomorrow" not in ql):
        periods = ", ".join(_AFTERNOON_PERIODS)
        q += f" (current day is {_dname(today)}, afternoon = periods {periods})"
        return q

    # ── 3. day before yesterday ────────────────────────────────────────────────
    if "day before yesterday" in ql:
        d = today - timedelta(days=2)
        q = q.replace("day before yesterday", f"{_fmt(d)} ({_dname(d)})")
        q = q.replace("Day before yesterday", f"{_fmt(d)} ({_dname(d)})")
        return q

    # ── 4. yesterday ──────────────────────────────────────────────────────────
    if "yesterday" in ql:
        d = today - timedelta(days=1)
        q = q.replace("yesterday", f"{_fmt(d)} ({_dname(d)})")
        q = q.replace("Yesterday", f"{_fmt(d)} ({_dname(d)})")
        return q

    # ── 5. day after tomorrow ─────────────────────────────────────────────────
    if "day after tomorrow" in ql:
        d = today + timedelta(days=2)
        q = q.replace("day after tomorrow", f"{_fmt(d)} ({_dname(d)})")
        q = q.replace("Day after tomorrow", f"{_fmt(d)} ({_dname(d)})")
        return q

    # ── 6. tomorrow / next day ─────────────────────────────────────────────────
    if "tomorrow" in ql or "next day" in ql:
        d = today + timedelta(days=1)
        q = q.replace("tomorrow", f"{_fmt(d)} ({_dname(d)})")
        q = q.replace("Tomorrow", f"{_fmt(d)} ({_dname(d)})")
        q = q.replace("next day", f"{_fmt(d)} ({_dname(d)})")
        q = q.replace("Next day", f"{_fmt(d)} ({_dname(d)})")
        return q

    # ── 7. today ──────────────────────────────────────────────────────────────
    if "today" in ql:
        q = q.replace("today", f"{_fmt(today)} ({_dname(today)})")
        q = q.replace("Today", f"{_fmt(today)} ({_dname(today)})")
        return q

    # ── 8. this week ──────────────────────────────────────────────────────────
    if "this week" in ql:
        week_start = today - timedelta(days=today.weekday())   # Monday
        week_end   = week_start + timedelta(days=4)            # Friday
        q += f" (this week = {_fmt(week_start)} to {_fmt(week_end)})"
        return q

    return q   # no temporal word found — pass through unchanged


def answer_query(user_query: str, top_k: int = 5, chat_history: list = None) -> dict:
    start = time.time()

    # ── Pre-resolve ALL relative date/time words in Python ───────────────────
    # The LLM parser has no idea what the actual date/time is.  We inject it
    # as unambiguous text so it only has to copy, never to compute.
    user_query = _inject_temporal_context(user_query)

    parsed = parse_query(user_query, chat_history=chat_history)
    print("PARSED:", parsed)
    print(f"PARSE TIME: {time.time() - start:.2f}s")
    
    intent = parsed.get("intent", "general")
    t2 = time.time()

    if intent == "timetable":
            from .timetable_extras import (
                query_full_day_timetable,
                query_faculty_timetable,
                query_free_periods,
                query_subject_schedule,
                query_class_at_period,
                format_timetable_chunks_v2,
                format_free_period_chunks,
            )
            if parsed.get("date"):
                exam_chunks = retrieve_chunks({"intent": "calendar", "date": parsed["date"]})
                exam_chunks = [c for c in exam_chunks if "exam" in c.get("content", "").lower()]
                if exam_chunks:
                    prompt = build_prompt(user_query, exam_chunks, params=parsed)
                    answer = generate_llm_answer(prompt, chat_history=chat_history)
                    return {"query": user_query, "answer": answer, "chunks_used": exam_chunks}
            # ── Free period query ──────────────────────────────────
            if parsed.get("free_period_query") and parsed.get("class") and parsed.get("day"):
                free_slots = query_free_periods(parsed["class"], parsed["day"])
                chunks = format_free_period_chunks(free_slots, parsed["class"], parsed["day"])

            # ── Faculty timetable ──────────────────────────────────
            elif parsed.get("faculty_timetable_query") and parsed.get("faculty_name"):
                raw_data = query_faculty_timetable(parsed["faculty_name"], parsed.get("day"))
                chunks = format_timetable_chunks_v2(raw_data)

            # ── Full day schedule for a class ─────────────────────
            elif parsed.get("full_day_query") and parsed.get("class") and parsed.get("day"):
                raw_data = query_full_day_timetable(parsed["class"], parsed["day"])
                chunks = format_timetable_chunks_v2(raw_data)

            # ── Subject schedule ("when is DBMS for 6A?") ─────────
            elif parsed.get("subject_schedule_query") and parsed.get("subject"):
                raw_data = query_subject_schedule(parsed["subject"], parsed.get("class"))
                chunks = format_timetable_chunks_v2(raw_data)

            # ── Cross-class: what is happening at a given slot ────
            elif parsed.get("day") and parsed.get("period") and not parsed.get("class"):
                raw_data = query_class_at_period(parsed["day"], parsed["period"])
                chunks = format_timetable_chunks_v2(raw_data)

            # ── Existing: specific class + day + (optional period) ─
            else:
                raw_data = query_timetable(parsed)   # your original function
                chunks = format_timetable_chunks_v2(raw_data)

    elif intent == "subjects":
        if parsed.get("is_class_teacher_query"):
            chunks = query_class_teacher(parsed)
            if not chunks:
                cls = parsed.get("class", "this class")
                return {
                    "query": user_query,
                    "answer": f"No class teacher has been assigned for {cls} yet.",
                    "chunks_used": []
                }
            teach_keywords = ["teach", "take", "handle", "subject", "which subject", "what subject"]
            if any(kw in user_query.lower() for kw in teach_keywords):
                ct_chunk = chunks[0]["content"]  # "The class teacher of 6A is Dr. Xyz."
                faculty_name = ct_chunk.split(" is ")[-1].rstrip(".")
                subject_params = {**parsed, "faculty_name": faculty_name, "class": None}
                raw_data = query_subjects(subject_params)
                chunks = format_subject_chunks(raw_data)
                if not chunks:
                    return {
                        "query": user_query,
                        "answer": f"{faculty_name} does not teach any subjects in the current semester.",
                        "chunks_used": []
                    }
        else:
            raw_data = query_subjects(parsed)
            chunks = format_subject_chunks(raw_data)
            if not chunks and parsed.get("faculty_name"):
                return {
                    "query": user_query,
                    "answer": f"{parsed['faculty_name']} do not teach any subjects in the current semester.",
                    "chunks_used": []
                }
            if "any lab" in user_query.lower():
                chunks = [c for c in chunks if "lab" in c["content"].lower().split("(code:")[0]]
                if not chunks:
                    return {"query": user_query, "answer": f"No, {parsed.get('faculty_name', 'this faculty')} does not teach any lab.", "chunks_used": []}

    elif intent == "calendar":
        chunks = retrieve_chunks(parsed)
    elif intent == "faculty":
        print("PARAMS SENT TO QUERY_FACULTY:", parsed)
        if parsed.get("direct_field") and parsed.get("faculty_name"):
            direct_answer = get_faculty_direct_field(
                faculty_name=parsed["faculty_name"],
                field=parsed["direct_field"]
            )
            if direct_answer:
                return {
                    "query": user_query,
                    "answer": direct_answer,
                    "chunks_used": []
                }

        raw_data = query_faculty(parsed)
        is_compact = parsed.get("is_list_query", False) or parsed.get("query_type") == "count"
        chunks = format_faculty_chunks(raw_data, compact=is_compact)

        # ── COUNT query: count directly from SQL, never let LLM count ──
        if parsed.get("query_type") == "count":
            exact_count = len(raw_data)
            designation = (parsed.get("designation") or "").strip()
            department  = (parsed.get("department") or "").strip()

            label = (designation if exact_count == 1 else designation + "s") if designation \
                    else ("faculty member" if exact_count == 1 else "faculty members")

            dept_suffix = f" in the {department.upper() if len(department) <= 4 else department.title()} department" \
                        if department else ""

            return {
                "query": user_query,
                "answer": f"There are {exact_count} {label}{dept_suffix}.",
                "chunks_used": chunks,
            }

        # ── LIST query: build answer in Python, never let LLM count ──
        if parsed.get("is_list_query"):
            exact_count = len(raw_data)
            designation = (parsed.get("designation") or "").strip()
            department = (parsed.get("department") or "").strip()

            label = (designation + "s") if designation else "faculty members"

            dept_suffix = f" in the {department.upper() if len(department) <= 4 else department.title()} department" \
                        if department else ""

            names = "\n".join(f"{i+1}. {r['name']}" for i, r in enumerate(raw_data))
            answer = f"There are {exact_count} {label}{dept_suffix}:\n{names}"

            return {
                "query": user_query,
                "answer": answer,
                "chunks_used": chunks,
            }
    elif intent == "lab":
        lab_query_type = parsed.get("lab_query_type")
        free_keywords = ["free", "occupied", "available", "busy"]
        if any(w in user_query.lower() for w in free_keywords):
            parsed["is_lab_free_query"] = True
        is_lab_free = parsed.get("is_lab_free_query", False)
        if is_lab_free:
            lab_names = parsed.get("lab_names")
            if lab_names:
                chunks = []
                for lab in lab_names:
                    parsed_copy = {**parsed, "lab_name": lab}
                    chunks.extend(query_lab_availability(parsed_copy))
            else:
                chunks = query_lab_availability(parsed)
        elif lab_query_type == "detail":
            if parsed.get("lab_keyword"):
                chunks = query_lab_by_keyword(parsed["lab_keyword"])
            else:
                chunks = query_lab_embeddings(parsed)
            if not chunks:
                chunks = retrieve_top_chunks(user_query, top_k)
        else:
            raw_data = query_lab(parsed)
            if parsed.get("is_list_query") and not parsed.get("min_computers") and not parsed.get("max_computers"):
                chunks = [
                    {
                        "content": f"{row.get('lab_name')} — Room {row.get('room_number')}",
                        "metadata": {},
                        "similarity": 1.0
                    }
                    for row in raw_data
                ]
            elif parsed.get("min_computers") or parsed.get("max_computers"):
                chunks = [
                    {
                        "content": f"{row.get('lab_name')} — Room {row.get('room_number')} — {row.get('no_of_computers')} computers",
                        "metadata": {},
                        "similarity": 1.0
                    }
                    for row in raw_data
                ]
            else:
                chunks = format_lab_chunks(raw_data)

    else:
        chunks = retrieve_top_chunks(user_query, top_k)

    print(f"SQL TIME: {time.time() - t2:.2f}s")

    # only return early for non-calendar intents
    if not chunks and intent != "calendar":
        return {
            "query": user_query,
            "answer": "No relevant information found in the knowledge base.",
            "chunks_used": [],
        }

    print("CHUNKS COUNT:", len(chunks))
    for c in chunks:
        print("CHUNK:", c["content"])
    prompt = build_prompt(user_query, chunks, params=parsed)

    t3 = time.time()
    answer = generate_llm_answer(prompt, chat_history=chat_history)
    print(f"LLM TIME: {time.time() - t3:.2f}s")
    print(f"TOTAL TIME: {time.time() - start:.2f}s")
    import re
    # fix numbers split across newlines e.g. "3\n8" → "38"
    answer = re.sub(r'(\d)\n(\d)', r'\1\2', answer)

    answer = answer.replace("\n- ", ", ")
    answer = answer.replace("\n", " ")
    answer = " ".join(answer.split())
    

    return {
        "query": user_query,
        "answer": answer,
        "chunks_used": chunks,
    }