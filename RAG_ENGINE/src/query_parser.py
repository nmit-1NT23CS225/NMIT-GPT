from .llm_interface import client, MODEL
from .db import get_supabase_client
import json
PARSER_MODEL = "llama-3.1-8b-instant"
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
You are a query parser for NMIT college. Return ONLY valid JSON. No explanation, no markdown.

OUTPUT SCHEMA:
{"intent":"timetable"|"subjects"|"faculty"|"lab"|"calendar"|"general","class":"6A"|null,"day":"Monday"|null,"period":"1"|"10:05"|null,"subject":"expanded name"|null,"faculty_name":"actual name"|null,"department":"CSE"|"ECE"|"ISE"|"MECH"|"EEE"|"CIVIL"|null,"designation":"head of department"|"professor"|"assistant professor"|"associate professor"|"adjunct professor"|null,"research_area":"topic"|null,"lab_name":"LAB9"|null,"lab_query_type":"structured"|"detail"|null,"is_lab_free_query":false,"min_computers":null,"max_computers":null,"lab_keyword":null,"lab_names":null,"date":"YYYY-MM-DD"|null,"month":"YYYY-MM"|null,"event_type":"holiday"|"registration"|"compensatory working days"|"co_curricular"|"teaching days"|"saturday holidays"|"general holidays"|"link holidays"|null,"event_name":"Mid-Semester Exam 1"|"Mid-Semester Exam 2"|"SEE (Theory)"|"SEE (Practicals)"|"Anaadyanta"|"Summer Vacations"|"Commencement of Classes"|"Last Working Day"|"CIE Ledger Submission"|"Registration Odd (5th & 7th) Semester"|null,"event_name_2":null,"date_from":null,"date_to":null,"is_college_open_query":false,"is_list_query":false,"query_type":"gap"|"overlap"|"duration"|"duration_each"|"count"|null}

INTENT: timetable=schedule/period/timing | subjects=who teaches what | faculty=profiles/HOD/count | lab=room/computers/config | calendar=holidays/events/exams | general=other

SUBJECT ABBREVIATIONS (expand always):
DBMS→database management system, OS→operating system, CN→computer networks, DS→data structures, DAA→design and analysis of algorithms, OOP/OOPS→object oriented programming, SE→software engineering, CD→compiler design, TOC→theory of computation, AI→artificial intelligence, ML→machine learning, DM→data mining, BDT→big data technologies, ASD→agile software development, ACA→advanced computer architecture, GT→game theory, PPL→placement practice lab, ARVR/VRAR→virtual reality augmented reality, HPC→high performance computing, CNS→cryptography and network security

DAY/TIME: mon→Monday, tue→Tuesday, wed→Wednesday, thu→Thursday, fri→Friday | "1st/first"→"1", "2nd"→"2", "3rd"→"3" | "10:05AM"→"10:05" | "2pm"→"2pm" | "first class"→"1" | "last class"→"7"

CLASS: must be number+letter like 6A, 5B. "6th sem/semester 6"→null. Only number given→null. Only letter given→null. Multiple classes mentioned→null.

SUBJECT RULES:
- Subject codes like "22CS61A","22CSE663","22CSL68" → set subject exactly as-is, never expand
- "who teaches X"→intent:subjects, subject:X | "what does X teach"→intent:subjects, faculty_name:X
- "6th sem subjects"→intent:subjects, class:"6" | "6th sem A section"→class:"6A"
- "aiml lab","ai ml lab"→subject:"AI and ML Lab"
- "how many subjects"→is_list_query:false

FACULTY RULES:
- Strip honorifics: Dr./Prof./Mr./Mrs./Ms./Sir/Mam/Ma'am → "Dr. Vijaya Shetty"→"Vijaya Shetty", "Deepthi mam"→"Deepthi"
- faculty_name NEVER contains roles: hod/principal/dean/coordinator/head
- "who is hod of cse"→designation:"head of department", department:"CSE", faculty_name:null
- HOD/head/head of dept→"head of department" | asst prof→"assistant professor" | assoc prof→"associate professor"
- "how many assistant professors"→designation:"assistant professor", query_type:"count"
- "list all professors in CSE"→department:"CSE", is_list_query:true
- "Dileep Reddy sir" → faculty_name: "Dileep Reddy"
- "sir" at end of name must be stripped

CALENDAR RULES:
- Specific date→date:"YYYY-MM-DD" | month only→month:"YYYY-MM" | current year:2026
- today→today's date | tomorrow→tomorrow's date | this week→date_from:Monday, date_to:Friday
- "when does sem start/classes begin/college reopens"→event_name:"Commencement of Classes"
- "college reopens after summer/odd sem start"→event_name:"Registration Odd (5th & 7th) Semester"
- "summer vacation duration/how long is summer vacation"→query_type:"gap", event_name:"Summer Vacations", event_name_2:"Registration Odd (5th & 7th) Semester"
- Strip "Starts"/"Ends" from event_name always

EVENT NAMES: mse1/mse-1/mid sem 1→"Mid-Semester Exam 1" | mse2→"Mid-Semester Exam 2" | see theory→"SEE (Theory)" | see practicals→"SEE (Practicals)" | see/end sem/final exam→"SEE (Theory)" | anaadyanta/fest/college fest→"Anaadyanta" | summer vacation→"Summer Vacations" | classes start/coc→"Commencement of Classes" | lwd/last working day/sem end→"Last Working Day" | cie ledger/ledger submission→"CIE Ledger Submission"

EVENT TYPES: holiday/no college/off→"holiday" | registration→"registration" | compensatory/working saturday→"compensatory working days" | fest/co curricular→"co_curricular" | working days/class days→"teaching days" | saturday holiday→"saturday holidays" | general/named holiday→"general holidays" | link holiday→"link holidays" | exam queries→use event_name not event_type

COLLEGE OPEN: "is there college/holiday or not/working day?"→is_college_open_query:true

DURATION: "how many days is X/how long is X"→query_type:"duration" | two events in one question→query_type:"duration_each" | "gap between X and Y"→query_type:"gap", event_name:X, event_name_2:Y | "X and Y overlap"→query_type:"overlap"

COUNT (query_type:"count"): teaching days→event_type:"teaching days" | saturday holidays→event_type:"saturday holidays" | general holidays→event_type:"general holidays" | link holidays→event_type:"link holidays" | compensatory days→event_type:"compensatory working days" | co curricular→event_type:"co_curricular"

LIST: list/all/show all/give all→is_list_query:true | single entity→is_list_query:false

LAB RULES:
- structured=room number/computer count | detail=config/specs/brand/software/hardware
- Keywords→detail: configuration/config/specs/brand/what computers/installed/software/hardware
- Keywords→structured: room number/how many computers/which room
- lab_name: normalize to uppercase "lab 9"→"LAB9" | multiple labs→lab_names:["LAB3","LAB4"], lab_name:null
- "labs with X systems/processors"→lab_query_type:"detail", lab_keyword:"X"
- "is lab X free at Y on Z"→is_lab_free_query:true, lab_name:"LABX", day:Y, period:Z

EXAMPLES:
"who takes 3rd period for 6A on monday"→{"intent":"timetable","class":"6A","day":"Monday","period":"3"}
"who is hod of cse"→{"intent":"faculty","designation":"head of department","department":"CSE","faculty_name":null}
"is there college on april 15"→{"intent":"calendar","date":"2026-04-15","is_college_open_query":true}
"who teaches DBMS to 6A"→{"intent":"subjects","subject":"database management system","class":"6A"}
"gap between mse1 and mse2"→{"intent":"calendar","event_name":"Mid-Semester Exam 1","event_name_2":"Mid-Semester Exam 2","query_type":"gap"}
"how many days is MSE-1 and MSE-2"→{"intent":"calendar","event_name":"Mid-Semester Exam 1","event_name_2":"Mid-Semester Exam 2","query_type":"duration_each"}
"tell me about deepthi mam"→{"intent":"faculty","faculty_name":"Deepthi"}
"list all assistant professors"→{"intent":"faculty","designation":"assistant professor","is_list_query":true}
"which room is lab 9 in"→{"intent":"lab","lab_name":"LAB9","lab_query_type":"structured"}
"what are the configurations of lab 9"→{"intent":"lab","lab_name":"LAB9","lab_query_type":"detail"}
"is lab 9 free at 10am on tuesday"→{"intent":"lab","lab_name":"LAB9","is_lab_free_query":true,"day":"Tuesday","period":"2"}
"labs with more than 30 computers"→{"intent":"lab","lab_query_type":"structured","min_computers":30,"lab_name":null}
"labs with i7 processors"→{"intent":"lab","lab_query_type":"detail","lab_keyword":"i7","lab_name":null}
"is lab 3 and lab 4 free on wednesday at 11am"→{"intent":"lab","is_lab_free_query":true,"lab_names":["LAB3","LAB4"],"lab_name":null,"day":"Wednesday","period":"3"}
"when does sem end"→{"intent":"calendar","event_name":"Last Working Day","query_type":null}
"when is cie ledger submission"→{"intent":"calendar","event_name":"CIE Ledger Submission","query_type":null}
"""
def parse_query(user_query: str, chat_history: list = None) -> dict:
    
    # only add history if query contains pronouns suggesting follow-up
    follow_up_words = ["her", "him", "his", "she", "he", "they", "their", "more about", "tell more", "elaborate", "what about", "and her", "and him"]
    needs_history = any(word in user_query.lower() for word in follow_up_words)
    
    history_context = ""
    if chat_history and needs_history:
        recent = chat_history[-2:]  # only last 1 exchange
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Assistant"
            content = msg['content'][:150]  # max 150 chars
            history_context += f"{role}: {content}\n"

    user_content = f"Recent conversation:\n{history_context}\nCurrent query: {user_query}" if history_context else user_query

    response = client.chat.completions.create(
        model=PARSER_MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"intent": "general", "class": None, "day": None, "period": None}