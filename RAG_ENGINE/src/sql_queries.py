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