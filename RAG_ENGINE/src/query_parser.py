from .llm_interface import client,MODEL
import json

PARSE_SYSTEM_PROMPT="""

You are a query parser for a college information system.

Extract structured parameters from the user's question and return ONLY a JSON object. No explanation, no markdown, just raw JSON.

{
  "intent": "timetable" | "subjects" | "faculty" | "lab" | "calendar" | "general",
  "class": "6A" | "5B" | null,
  "day": "Monday" | "Tuesday" | "Wednesday" | "Thursday" | "Friday" | null,
  "period": "1" | "2" | "3" | "9:00" | "10:05" | "11:00" | "10am" | "2pm" | null,
  "subject": "database management system" | null,
  "faculty_name": "Vijaya Shetty" | null,
  "lab_name": null | "lab name here"
  "date": "2026-04-01" | null
  "department": "CSE" | "ECE" | "ISE" | null,
  "designation": "HOD" | "Professor" | "Assistant Professor" | null,
  "research_area": "machine learning" | "cloud computing" | null,
  
}

Rules:
- Expand abbreviations: DBMS → database management system, OS → operating system, CN → computer networks
- Normalize day: mon → Monday, tue → Tuesday, wed → Wednesday, thu → Thursday, fri → Friday
- Normalize period: "3rd period" → "3", "third" → "3", "10:05AM" → "10:05", "2pm" → "2pm"
- class looks like 6A, 5B, 4C etc — extract exactly as mentioned
- If a field is not mentioned, set it to null
- intent must be the single best match
- If the question is about holidays, events, exams, dates → intent is "calendar"
- Extract date as "date": "YYYY-MM-DD" format. April 1st → "2026-04-01"
- If question is about a faculty member's profile, email, experience, research, achievements, subjects taught, qualifications → intent is "faculty"
- If a department is mentioned (CSE, ECE, ISE etc.) and asking about people → intent is "faculty"
- Strip honorifics from names: "Dr. Sharma" → "Sharma", "Prof. Vijaya" → "Vijaya"

"""
def parse_query(user_query: str)->dict:
    """Use LLM to extract structured intent and parameters from the query."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        temperature=0  
    )
    
    raw = response.choices[0].message.content.strip()
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # fallback if LLM misbehaves
        return {"intent": "general", "class": None, "day": None, "period": None}