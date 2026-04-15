from .db import get_supabase_client

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

    if params.get("date"):
        query = query.eq("event_date", params["date"])

    result = query.execute()
    return result.data


def format_calendar_chunks(data: list) -> list:
    chunks = []
    for row in data:
        text = (
            f"On {row.get('event_date')}, "
            f"{row.get('event_name')} "
            f"({row.get('event_type')})."
        )
        if row.get("description"):
            text += f" {row.get('description')}"

        chunks.append({
            "content": text,
            "metadata": {"source_type": "calendar"},
            "similarity": 1.0
        })
    return chunks
def query_faculty(params: dict) -> list:
    """
    Bulletproof faculty query — handles any twisted query about faculty_biodata.
    Strategy:
      1. Apply structured filters if params are present
      2. If nothing found, fetch ALL faculty (LLM will extract from full context)
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

    # Filter by name (fuzzy — handles "sharma", "Dr. Sharma", "sharma sir")
    if params.get("faculty_name"):
        name = params["faculty_name"].strip()
        # strip honorifics so "Dr. Vijaya" → "Vijaya"
        for honorific in ["dr.", "dr ", "prof.", "prof ", "mr.", "mr ", "ms.", "ms ", "mrs.", "mrs "]:
            name = name.lower().replace(honorific, "").strip()
        query = query.ilike("name", f"%{name}%")
        filters_applied = True

    # ---------------------------------------------------------
    # SMART FILTERING: Department (CSE Scoped)
    # ---------------------------------------------------------
    if params.get("department"):
        dept = params["department"].lower()
        
        # Only handle CSE translations for now
        if "cse" in dept or "cs" in dept:
            dept_search = "computer"  # Will match "Computer Science" or "Computer Science and Engineering"
        else:
            dept_search = dept # Fallback to whatever was extracted
            
        query = query.ilike("department", f"%{dept_search}%")
        filters_applied = True

    # ---------------------------------------------------------
    # SMART FILTERING: Designation (Handles HOD / Asst Prof)
    # ---------------------------------------------------------
    if params.get("designation"):
        desig = params["designation"].lower()
        
        # Translate shortforms to the actual words used in your database
        if "hod" in desig or "head" in desig:
            desig_search = "head"  # This will successfully match "professor , head"
        elif "asst" in desig or "assistant" in desig:
            desig_search = "assistant"
        elif "prof" in desig:
            desig_search = "professor"
        else:
            desig_search = desig
            
        query = query.ilike("designation", f"%{desig_search}%")
        filters_applied = True

    # Filter by subject (checks subjects_taught array column)
    if params.get("subject"):
        # Supabase array contains — works if subjects_taught is a text[] column
        query = query.contains("subjects_taught", [params["subject"]])
        filters_applied = True

    # Filter by area of interest / research
    if params.get("research_area"):
        # areas_of_interest is an array (text[]), so we must use .contains() instead of .ilike()
        query = query.contains("areas_of_interest", [params["research_area"]])
        filters_applied = True

    result = query.execute().data

    # FALLBACK: if filters returned nothing, fetch ALL faculty
    # The LLM will read full context and still answer correctly
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

def format_faculty_chunks(data: list) -> list:
    """Convert faculty_biodata rows into clean text chunks for the LLM."""
    chunks = []
    for f in data:
        # Build a rich natural language description of each faculty
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
        if f.get("education_qualification"):
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
        if f.get("orchid_id"):
            lines.append(f"ORCID ID: {f['orcid_id']}")
        if f.get("linkedid"):
            lines.append(f"LinkedIn: {f['linkedin_id']}")

        text = "\n".join(lines)
        chunks.append({
            "content": text,
            "metadata": {"source_type": "faculty_biodata", "name": f.get("name")},
            "similarity": 1.0
        })

    return chunks