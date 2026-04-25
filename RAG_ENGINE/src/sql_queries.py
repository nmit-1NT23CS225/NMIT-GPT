from .db import get_supabase_client
import calendar as cal_module
from collections import defaultdict
import re
TIME_SLOT_MAP = {
    # by period number
    "1": "09:00-09:55",
    "2": "10:05-11:00",
    "3": "11:00-11:55",
    "4": "12:35-01:30",
    "5": "01:30-02:25",
    "6": "02:25-03:20",
    "7": "03:20-04:15",

    # by natural time mentions
    "9am": "09:00-09:55",
    "9:00": "09:00-09:55",
    "10am": "10:05-11:00",
    "10:05": "10:05-11:00",
    "11am": "11:00-11:55",
    "11:00": "11:00-11:55",
    "12pm": "12:35-01:30",
    "12:35": "12:35-01:30",
    "1pm": "01:30-02:25",
    "1:30": "01:30-02:25",
    "2pm": "02:25-03:20",
    "2:25": "02:25-03:20",
    "3pm": "03:20-04:15",
    "3:20": "03:20-04:15",
}
EVENT_TYPE_MAP = {
    "semester end": "exam",
    "sem end": "exam",
    "see": "exam",
    "mid sem": "exam",
    "midsem": "exam",
    "mse": "exam",
    "midterm": "exam",
    "final exam": "exam",
    "backlog": "registration",
    "sem registration": "registration",
    "compensatory": "compensatory working day",
    "extra working": "compensatory working day",
    "co_curricular": "co_curricular",
    "fest": "co_curricular",
    "cultural": "co_curricular",
}
def normalize_event_type(event_type: str) -> str:
    if not event_type:
        return None
    lower = event_type.lower().strip()
    for key, val in EVENT_TYPE_MAP.items():
        if key in lower:
            return val
    return lower

def query_timetable(params: dict) -> list:
    supabase = get_supabase_client()

    query = supabase.table("timetable").select("*")

    if params.get("class"):
        query = query.eq("class", params["class"])
    if params.get("day"):
        query = query.eq("day_of_week", params["day"])
    if params.get("period"):
        # resolve period/time to actual DB time slot
        raw = str(params["period"]).lower().strip()
        time_slot = TIME_SLOT_MAP.get(raw)
        if time_slot:
            query = query.eq("time_slot", time_slot)

    timetable_rows = query.execute().data
    
    if not timetable_rows:
        return []

    # STEP 2: get all subject codes from results
    subject_codes = list({row["subject_code"] for row in timetable_rows if row.get("subject_code")})

    # STEP 3: fetch matching subjects + faculty
    subjects_rows = supabase.table("subjects") \
        .select("subject_code, subject_name, class, faculty_id, faculty_biodata(name)") \
        .in_("subject_code", subject_codes) \
        .execute().data

    # STEP 4: build a lookup dict
    subject_map = {row["subject_code"]: row for row in subjects_rows}

    # STEP 5: merge timetable + subject info
    for row in timetable_rows:
        row["subject_info"] = subject_map.get(row["subject_code"], {})

    return timetable_rows


def query_subjects(params: dict) -> list:
    """Fetch subject/faculty data using exact SQL filters."""
    supabase = get_supabase_client()

    query = supabase.table("subjects") \
        .select("""
            subject_name,
            subject_code,
            class,
            faculty_biodata(name),
            lab_infrastructure(lab_name, room_number)
        """)

    if params.get("subject"):
        query = query.ilike("subject_name", f"%{params['subject']}%")

    if params.get("class"):
        query = query.eq("class", params["class"])

    result = query.execute()
    return result.data

def query_calendar(params: dict) -> list:
    supabase = get_supabase_client()

    query = supabase.table("academic_calendar").select("*")

    if params.get("event_name"):
        query = query.ilike("event_name", f"%{params['event_name']}%")

    else:
        if params.get("date"):
            query = query.eq("event_date", params["date"])
            # don't filter by event_type for specific date queries
            # fetch everything on that date and let LLM reason

        elif params.get("month"):
            month = params["month"]
            year, mon = month.split("-")
            last_day = cal_module.monthrange(int(year), int(mon))[1]
            query = query.gte("event_date", f"{month}-01").lte("event_date", f"{month}-{last_day:02d}")
            # apply event_type filter only for month queries
            if params.get("event_type"):
                normalized = normalize_event_type(params["event_type"])
                if normalized:
                    query = query.ilike("event_type", f"%{normalized}%")

        elif params.get("date_from") and params.get("date_to"):
            query = query.gte("event_date", params["date_from"]).lte("event_date", params["date_to"])
            if params.get("event_type"):
                normalized = normalize_event_type(params["event_type"])
                if normalized:
                    query = query.ilike("event_type", f"%{normalized}%")

    query = query.order("event_date", desc=False)
    return query.execute().data



def format_calendar_chunks(data: list, params: dict = None) -> list:
    if not data:
        return []

    chunks = []

    # handle "is there college on X date?" queries
    if params and params.get("is_college_open_query") and params.get("date"):
        date = params["date"]
        holidays = [r for r in data if "holiday" in r.get("event_type", "").lower()]
        comp_days = [r for r in data if "compensatory" in r.get("event_type", "").lower()]

        if holidays:
            names = ", ".join(r.get("event_name", "") for r in holidays)
            text = f"On {date}, college is CLOSED. It is a holiday: {names}."
        elif comp_days:
            names = ", ".join(r.get("event_name", "") for r in comp_days)
            text = f"On {date}, college is OPEN. It is a compensatory working day: {names}."
        else:
            names = ", ".join(r.get("event_name", "") for r in data)
            text = f"On {date}, there is an event: {names}. College schedule may vary."

        chunks.append({
            "content": text,
            "metadata": {"source_type": "calendar"},
            "similarity": 1.0
        })
        return chunks

    # normalize event names — group "SEE (Theory) Starts" with "SEE (Theory)" but keep "Ends" separate
    def normalize_event_group(name: str) -> str:
        cleaned = re.sub(r'\s*(Starts?)$', '', name, flags=re.IGNORECASE).strip()
        return cleaned

    # group by normalized event name
    grouped = defaultdict(list)
    for row in data:
        key = normalize_event_group(row.get("event_name", "Unknown"))
        grouped[key].append(row)

    for event_name, rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: r.get("event_date", ""))
        dates = [r.get("event_date") for r in rows_sorted]
        event_type = rows_sorted[0].get("event_type", "")
        description = rows_sorted[0].get("description", "")

        # check original event names to detect start/end context
        original_names = [r.get("event_name", "") for r in rows_sorted]
        has_start = any(re.search(r'\bStarts?\b', n, re.IGNORECASE) for n in original_names)
        has_end = any(re.search(r'\bEnds?\b', n, re.IGNORECASE) for n in original_names)

        if len(dates) == 1:
            if has_start:
                text = f"'{event_name}' ({event_type}) starts on {dates[0]}."
            elif has_end:
                text = f"'{event_name}' ({event_type}) ends on {dates[0]}."
            else:
                text = f"'{event_name}' ({event_type}) is on {dates[0]}."
        else:
            text = f"'{event_name}' ({event_type}) starts on {dates[0]} and ends on {dates[-1]}."

        if description:
            text += f" Details: {description}."

        if "holiday" in event_type.lower():
            text += " College is CLOSED on these days."
        elif "compensatory" in event_type.lower():
            text += " College is OPEN on these days."
        elif "exam" in event_type.lower():
            text += " Exams are scheduled during this period."
        elif "registration" in event_type.lower():
            text += " Registration is scheduled during this period."

        chunks.append({
            "content": text,
            "metadata": {"source_type": "calendar"},
            "similarity": 1.0
        })

    return chunks


def retrieve_chunks(params: dict) -> list:
    """
    Smart calendar retrieval — handles all calendar query types.
    Wraps query_calendar + format_calendar_chunks with special logic
    for gap, duration, overlap, and college open queries.
    """
    supabase = get_supabase_client()
    query_type = params.get("query_type")

    # GAP or OVERLAP between two events
    if query_type in ("gap", "overlap") and params.get("event_name") and params.get("event_name_2"):
        # fetch event 1
        result1 = supabase.table("academic_calendar").select("*") \
            .ilike("event_name", f"%{params['event_name']}%") \
            .order("event_date", desc=False).execute().data

        # fetch event 2
        result2 = supabase.table("academic_calendar").select("*") \
            .ilike("event_name", f"%{params['event_name_2']}%") \
            .order("event_date", desc=False).execute().data

        chunks = []

        if result1:
            dates1 = [r["event_date"] for r in result1]
            chunks.append({
                "content": f"'{params['event_name']}' runs from {dates1[0]} to {dates1[-1]}.",
                "metadata": {"source_type": "calendar"},
                "similarity": 1.0
            })

        if result2:
            dates2 = [r["event_date"] for r in result2]
            chunks.append({
                "content": f"'{params['event_name_2']}' runs from {dates2[0]} to {dates2[-1]}.",
                "metadata": {"source_type": "calendar"},
                "similarity": 1.0
            })

        return chunks

    # DURATION of a single event
    if query_type == "duration" and params.get("event_name"):
        result = supabase.table("academic_calendar").select("*") \
            .ilike("event_name", f"%{params['event_name']}%") \
            .order("event_date", desc=False).execute().data

        if not result:
            return []

        dates = [r["event_date"] for r in result]
        text = f"'{params['event_name']}' runs from {dates[0]} to {dates[-1]}, spanning {len(dates)} days."
        return [{
            "content": text,
            "metadata": {"source_type": "calendar"},
            "similarity": 1.0
        }]

    # DEFAULT — use existing query_calendar + format_calendar_chunks
    data = query_calendar(params)
    return format_calendar_chunks(data, params=params)
def format_faculty_chunks(data: list, compact: bool = False) -> list:
    """Convert faculty_biodata rows into clean text chunks for the LLM."""
    chunks = []
    for f in data:
        if compact:
            text = (
                f"Name: {f.get('name')} | "
                f"Designation: {f.get('designation')} | "
                f"Department: {f.get('department')}"
            )
        else:
            lines = []
            if f.get("name"):
                lines.append(f"Name: {f['name']}")
            if f.get("faculty_shortform"):
                lines.append(f"Short name / initials: {f['faculty_shortform']}")
            if f.get("designation"):
                lines.append(f"Designation: {f['designation']}")
            if f.get("department"):
                lines.append(f"Department: {f['department']}")
            if f.get("email"):
                lines.append(f"Email: {f['email']}")
            if f.get("joining_date"):
                lines.append(f"Joining Date: {f['joining_date']}")
            if f.get("past_experience"):
                lines.append(f"Past Experience: {f['past_experience']}")
            if f.get("educational_qualifications"):
                lines.append(f"Education: {f['educational_qualifications']}")
            if f.get("areas_of_interest"):
                lines.append(f"General Topics of Interest: {f['areas_of_interest']}")
            if f.get("research"):
                lines.append(f"Funded Research Projects & Grants: {f['research']}")
            if f.get("achievements"):
                lines.append(f"Achievements: {f['achievements']}")
            if f.get("subjects_taught"):
                subjects = f["subjects_taught"]
                if isinstance(subjects, list):
                    subjects = ", ".join(subjects)
                lines.append(f"Subjects Taught: {subjects}")
            if f.get("scholar_id"):
                lines.append(f"Google Scholar ID: {f['scholar_id']}")
            if f.get("orcid_id"):
                lines.append(f"ORCID ID: {f['orcid_id']}")
            if f.get("linkedin_id"):
                lines.append(f"LinkedIn: {f['linkedin_id']}")

            text = "\n".join(lines)

        chunks.append({
            "content": text,
            "metadata": {"source_type": "faculty_biodata", "name": f.get("name")},
            "similarity": 1.0
        })
    return chunks

def query_faculty(params: dict) -> list:
    """
    Bulletproof faculty query — handles any twisted query about faculty_biodata.
    """
    supabase = get_supabase_client()

    query = supabase.table("faculty_biodata").select("""
        faculty_id,
        name,
        designation,
        department,
        email,
        joining_date,
        past_experience,
        educational_qualifications,
        areas_of_interest,
        achievements,
        subjects_taught,
        scholar_id,
        orcid_id,
        linkedin_id,
        research,
        faculty_shortform
    """)

    filters_applied = False

    # Filter by name
    if params.get("faculty_name"):
        name = params["faculty_name"].strip().lower()
        for honorific in ["dr.", "dr ", "prof.", "prof ", "mr.", "mr ", "ms.", "ms ", "mrs.", "mrs "]:
            name = name.replace(honorific, "").strip()
        role_phrases = [
            "hod of cse", "hod of ise", "hod of ece", "hod of cs",
            "hod of eee", "hod of mech", "hod of civil",
            "hod", "head of department", "head of dept",
            "principal", "dean", "coordinator"
        ]
        for phrase in role_phrases:
            name = name.replace(phrase, "").strip()
        if name:
            query = query.ilike("name", f"%{name}%")
            filters_applied = True

    # Filter by department
    if params.get("department"):
        dept = params["department"].lower()
        if "cse" in dept or "cs" in dept:
            dept_search = "computer"
        else:
            dept_search = dept
        query = query.ilike("department", f"%{dept_search}%")
        filters_applied = True

    # Filter by designation
    if params.get("designation"):
        desig = params["designation"].lower()
        if "hod" in desig or "head" in desig:
            desig_search = "head"
        elif "assistant" in desig or "asst" in desig:
            desig_search = "assistant professor"
        elif "associate" in desig:
            desig_search = "associate professor"
        elif "adjunct" in desig:
            desig_search = "adjunct"
        elif "prof" in desig:
            desig_search = "professor"
        else:
            desig_search = desig
        query = query.ilike("designation", f"%{desig_search}%")
        filters_applied = True
        print("DESIGNATION FILTER USED:", desig_search)  # 👈 inside block

    # Filter by subject
    if params.get("subject"):
        query = query.contains("subjects_taught", [params["subject"]])
        filters_applied = True

    # Filter by research area
    if params.get("research_area"):
        query = query.contains("areas_of_interest", [params["research_area"]])
        filters_applied = True

    result = query.execute().data
    print("RESULT COUNT:", len(result))

    # FALLBACK
    if not result:
        result = supabase.table("faculty_biodata").select("""
            faculty_id,
            name,
            designation,
            department,
            email,
            joining_date,
            past_experience,
            educational_qualifications,
            areas_of_interest,
            achievements,
            subjects_taught,
            scholar_id,
            orcid_id,
            linkedin_id,
            research,
            faculty_shortform
        """).limit(5).execute().data

    return result
