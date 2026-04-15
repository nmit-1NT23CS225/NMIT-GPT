from .llm_interface import client, MODEL
from .db import get_supabase_client
import json

# fetch once at startup, reuse for all queries
def _load_event_names() -> list:
    try:
        supabase = get_supabase_client()
        result = supabase.table("academic_calendar").select("event_name").execute()
        return list({row["event_name"] for row in result.data if row.get("event_name")})
    except Exception:
        return []

KNOWN_EVENT_NAMES = _load_event_names()

PARSE_SYSTEM_PROMPT = """
You are a query parser for a college information system.

Extract structured parameters from the user's question and return ONLY a JSON object. No explanation, no markdown, just raw JSON.

{
  "intent": "timetable" | "subjects" | "faculty" | "lab" | "calendar" | "general",
  "class": "6A" | "5B" | null,
  "day": "Monday" | "Tuesday" | "Wednesday" | "Thursday" | "Friday" | null,
  "period": "1" | "2" | "3" | "9:00" | "10:05" | "11:00" | "10am" | "2pm" | null,
  "subject": "database management system" | null,
  "faculty_name": "Vijaya Shetty" | null,
  "department": "CSE" | "ECE" | "ISE" | "MECH" | null,
  "designation": "HOD" | "Professor" | "Assistant Professor" | null,
  "research_area": "machine learning" | "cloud computing" | null,
  "lab_name": null | "lab name here",
  "date": "2026-04-01" | null,
  "month": "2026-04" | null,
  "event_type": "holiday" | "exam" | "event" | "registration" | "compensatory working day" | "co_curricular" | null,
  "event_name": "MSE-1" | "MSE-2" | "SEE" | "Anaadyanta" | null,
  "date_from": "2026-04-01" | null,
  "date_to": "2026-04-10" | null,
  "is_college_open_query": true | false
}

Rules:
- Expand abbreviations: DBMS → database management system, OS → operating system, CN → computer networks
- Normalize day: mon → Monday, tue → Tuesday, wed → Wednesday, thu → Thursday, fri → Friday
- Normalize period: "3rd period" → "3", "third" → "3", "10:05AM" → "10:05", "2pm" → "2pm"
- class looks like 6A, 5B, 4C etc — extract exactly as mentioned
- If a field is not mentioned, set it to null
- intent must be the single best match

Intent Detection:
- If the question is about holidays, events, exams, dates, college open/closed → intent is "calendar"
- If question is about a faculty member's profile, email, experience, research, achievements, subjects taught, qualifications → intent is "faculty"
- If a department is mentioned (CSE, ECE, ISE etc.) and asking about people → intent is "faculty"

Faculty Rules:
- Strip honorifics from names: "Dr. Sharma" → "Sharma", "Prof. Vijaya" → "Vijaya"

Calendar Rules:
- Extract date as "date": "YYYY-MM-DD" format ONLY if a specific date is mentioned like "April 1st"
- Extract month as "month": "YYYY-MM" format. "in April" → "2026-04"
- DO NOT set date if no specific date is mentioned in the question
- For date ranges: "between April 1 and April 10" → date_from: "2026-04-01", date_to: "2026-04-10"
- Current year is 2026

event_name mapping (VERY IMPORTANT):
- "mse 1", "mse1", "mid sem 1", "first mid sem", "midsem 1" → "MSE-1"
- "mse 2", "mse2", "mid sem 2", "second mid sem", "midsem 2" → "MSE-2"
- "mse", "mid sem", "midsem", "midterm" (no number) → "MSE"
- "see", "sem end", "end sem", "semester end", "final exam", "see theory", "see practical" → "SEE"
- "anaadyanta", "anaadyantha", "anadyanta", "anadyantha" → "Anaadyanta"
- Match user query to the closest name from KNOWN_EVENT_NAMES and set as event_name. Handle typos.

event_type mapping:
- "holiday", "holidays", "no college", "off" → "holiday"
- "registration", "registrations", "backlog registration" → "registration"
- "compensatory", "compensatory working day" → "compensatory working day"
- "event", "fest", "function" → "event"
- "fest", "cultural", "co curricular", "co-curricular", "anaadyanta" → "co_curricular"
- For exam related → set event_name instead of event_type

is_college_open_query:
- "is there college on X?", "do we have college?", "is college open?", "holiday or not?" → true
- everything else → false
"""

def parse_query(user_query: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Known calendar events: {KNOWN_EVENT_NAMES}\n\nUser query: {user_query}"}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"intent": "general", "class": None, "day": None, "period": None}