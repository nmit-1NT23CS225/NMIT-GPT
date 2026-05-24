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
    # For holidays with multiple dates → list each date individually
            if "holiday" in event_type.lower():
                for date in dates:
                    individual_text = f"'{event_name}' ({event_type}) is on {date}. College is CLOSED on these days."
                    chunks.append({
                        "content": individual_text,
                        "metadata": {"source_type": "calendar"},
                        "similarity": 1.0
                    })
                continue  # skip the append at the bottom for this group
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


from datetime import date, timedelta
import re


def retrieve_chunks(params: dict) -> list:
    supabase    = get_supabase_client()
    query_type  = params.get("query_type")
    event_name  = (params.get("event_name")  or "").strip()
    event_name2 = (params.get("event_name_2") or "").strip()

    # ─────────────────────────────────────────────────────────────────────────
    # LOW-LEVEL HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def make_chunk(content: str) -> dict:
        return {"content": content, "metadata": {"source_type": "calendar"}, "similarity": 1.0}

    def iter_dates(start_str: str, end_str: str):
        """Yield every date from start to end inclusive."""
        cur = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
        while cur <= end:
            yield cur
            cur += timedelta(days=1)

    def fetch_all_rows() -> list:
        return (
            supabase.table("academic_calendar")
            .select("*")
            .order("event_date", desc=False)
            .execute()
            .data
        )

    def fetch_by_name(name: str) -> list:
        return (
            supabase.table("academic_calendar")
            .select("*")
            .ilike("event_name", f"%{name}%")
            .order("event_date", desc=False)
            .execute()
            .data
        )

    def fetch_by_type(event_type: str, date_from: str = None, date_to: str = None) -> list:
        q = supabase.table("academic_calendar").select("*").eq("event_type", event_type)
        if date_from:
            q = q.gte("event_date", date_from)
        if date_to:
            q = q.lte("event_date", date_to)
        return q.order("event_date", desc=False).execute().data

    def fetch_in_range(date_from: str, date_to: str) -> list:
        return (
            supabase.table("academic_calendar")
            .select("*")
            .gte("event_date", date_from)
            .lte("event_date", date_to)
            .order("event_date", desc=False)
            .execute()
            .data
        )

    def boundary_dates(rows: list) -> tuple:
        """
        Return (start_date, end_date) for a list of rows.
        Prefers explicit 'Starts'/'Ends' marker rows; falls back to first/last date.
        """
        if not rows:
            return None, None
        start_rows = [r for r in rows if re.search(r"\bStarts?\b", r.get("event_name", ""), re.IGNORECASE)]
        end_rows   = [r for r in rows if re.search(r"\bEnds?\b",   r.get("event_name", ""), re.IGNORECASE)]
        start = start_rows[0]["event_date"] if start_rows else rows[0]["event_date"]
        end   = end_rows[-1]["event_date"]  if end_rows   else rows[-1]["event_date"]
        return start, end

    def non_teaching_dates_in_range(date_from: str, date_to: str) -> set:
        """
        Return set of ISO date strings that are non-teaching within [date_from, date_to].
        Excludes: holidays, co_curricular days, vacation, registration, exam days.
        Does NOT include Sundays (handled separately via weekday check).
        Does NOT exclude 'academic' rows (compensatory working days count as teaching).
        """
        rows = fetch_in_range(date_from, date_to)
        return {
    r["event_date"] for r in rows
    if r["event_type"] in ("holiday", "exam", "vacation", "co_curricular")
}

    def count_working_days(start_str: str, end_str: str) -> int:
        """
        Count days in [start, end] that are NOT Sundays and NOT non-teaching days.
        Non-teaching = holiday, co_curricular, vacation, registration, exam.
        """
        print(non_teaching_dates_in_range(start_str, end_str))
        excluded = non_teaching_dates_in_range(start_str, end_str)
        count = 0
        for d in iter_dates(start_str, end_str):
            if d.weekday() != 6 and d.isoformat() not in excluded:
                count += 1
        
        return count
    def count_exam_days(start_str: str, end_str: str) -> int:
        """For exam duration: exclude Sundays and holidays only."""
        rows = fetch_in_range(start_str, end_str)
        holiday_dates = {
            r["event_date"] for r in rows
            if r["event_type"] == "holiday"
        }
        return sum(
            1 for d in iter_dates(start_str, end_str)
            if d.weekday() != 6 and d.isoformat() not in holiday_dates
        )
    def exam_actual_rows(rows: list) -> list:
        """Remove Start/End marker rows — keep only actual exam day rows."""
        return [
            r for r in rows
            if not re.search(r"\b(Starts?|Ends?)\b", r.get("event_name", ""), re.IGNORECASE)
        ]

    def infer_end_from_next_event(start_date: str, current_event_type: str = None) -> str:
        """
        Infer the end date of an event that has no 'Ends' marker.
        Looks for the next event in the DB that is a DIFFERENT event (not same name/type),
        and returns the day before it as the inferred end date.

        For SEE Practicals (exam type): end = day before SEE Theory Starts.
        For Summer Vacations (vacation type): end = day before next registration/academic event.
        """
        all_rows = fetch_all_rows()

        # Find next event date strictly after start_date that signals end of this event.
        # Priority: look for the next exam marker (Starts/Ends) or next non-holiday event.
        later_rows = [r for r in all_rows if r["event_date"] > start_date]

        if current_event_type == "exam":
            # For exams: end = day before the next exam 'Starts' or 'Ends' marker
            # that is NOT the same event
            for r in later_rows:
                if r["event_type"] == "exam" and re.search(r"\bStarts?\b", r.get("event_name", ""), re.IGNORECASE):
                    return (date.fromisoformat(r["event_date"]) - timedelta(days=1)).isoformat()

        if current_event_type == "vacation":
            # For vacation: end = day before next registration or academic (non-holiday) event
            skip_types = {"holiday"}
            for r in later_rows:
                if r["event_type"] not in skip_types:
                    return (date.fromisoformat(r["event_date"]) - timedelta(days=1)).isoformat()

        # Generic fallback: day before the next event of any type
        later_dates = sorted({r["event_date"] for r in later_rows})
        if not later_dates:
            return start_date
        return (date.fromisoformat(later_dates[0]) - timedelta(days=1)).isoformat()
 # ─────────────────────────────────────────────────────────────────────────
# SUMMER VACATION DURATION — special case
# ─────────────────────────────────────────────────────────────────────────
    if query_type == "duration" and event_name == "Summer Vacations":
        vacation_rows = fetch_by_name("Summer Vacations")
        reg_rows = fetch_by_name("Registration Odd (5th & 7th) Semester")

        if not vacation_rows:
            return [make_chunk("No data found for Summer Vacations.")]
        if not reg_rows:
            return [make_chunk("No data found for Odd Semester Registration.")]

        start_date = vacation_rows[0]["event_date"]
        end_date = (date.fromisoformat(reg_rows[0]["event_date"]) - timedelta(days=1)).isoformat()

        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
        duration = (end_d - start_d).days + 1

        return [make_chunk(
            f"Summer Vacations start on {start_date} and end on {end_date}, "
            f"spanning {duration} days."
        )]
    # ─────────────────────────────────────────────────────────────────────────
    # DURATION of a single event
    # ─────────────────────────────────────────────────────────────────────────
    if query_type == "duration" and event_name:
        clean = re.sub(r"\s*(Starts?|Ends?)$", "", event_name, flags=re.IGNORECASE).strip()
        rows  = fetch_by_name(clean)

        if not rows:
            return [make_chunk(f"No calendar data found for '{clean}'.")]

        start_date, end_date = boundary_dates(rows)
        actual_rows = exam_actual_rows(rows)

        if actual_rows:
            # MSE-style: one DB row per exam day — count directly
            duration = len(actual_rows)
            return [make_chunk(
                f"'{clean}' runs from {start_date} to {end_date}, spanning {duration} days."
            )]

        # SEE-style: only Starts/Ends markers in DB → count working days in range
        # Vacation-style: single row → infer end from next event, count calendar days
        row_event_type = rows[0].get("event_type") if rows else None
        is_vacation    = any(r.get("event_type") == "vacation" for r in rows)

        if start_date == end_date:
            # Single marker row — infer end date from next event
            end_date = infer_end_from_next_event(start_date, current_event_type=row_event_type)

        if is_vacation:
            # Vacation: count all calendar days (including Sundays)
            start_d  = date.fromisoformat(start_date)
            end_d    = date.fromisoformat(end_date)
            duration = (end_d - start_d).days + 1
        elif row_event_type == "exam":
            # Exams: count non-Sundays, exclude holidays but NOT exam rows
            duration = count_exam_days(start_date, end_date)
        else:
            # SEE: count non-Sunday, non-holiday days
            duration = count_working_days(start_date, end_date)

        return [make_chunk(
            f"'{clean}' runs from {start_date} to {end_date}, spanning {duration} days."
        )]

    # ─────────────────────────────────────────────────────────────────────────
    # DURATION_EACH — "how many days is MSE-1 and MSE-2?"
    # ─────────────────────────────────────────────────────────────────────────
    if query_type == "duration_each" and event_name and event_name2:
        chunks = []
        for name in (event_name, event_name2):
            clean = re.sub(r"\s*(Starts?|Ends?)$", "", name, flags=re.IGNORECASE).strip()
            rows  = fetch_by_name(clean)
            if not rows:
                chunks.append(make_chunk(f"No data found for '{clean}'."))
                continue
            start_date, end_date = boundary_dates(rows)
            actual_rows = exam_actual_rows(rows)
            if actual_rows:
                duration = len(actual_rows)
            else:
                row_event_type = rows[0].get("event_type") if rows else None
                if start_date == end_date:
                    end_date = infer_end_from_next_event(start_date, current_event_type=row_event_type)
                is_vac = any(r.get("event_type") == "vacation" for r in rows)
                if is_vac:
                    duration = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
                elif row_event_type == "exam":
                    duration = count_exam_days(start_date, end_date)
                else:
                    duration = count_working_days(start_date, end_date)
            chunks.append(make_chunk(
                f"'{clean}' runs from {start_date} to {end_date}, spanning {duration} days."
            ))
        return chunks

    # ─────────────────────────────────────────────────────────────────────────
    # GAP / OVERLAP between two events
    # ─────────────────────────────────────────────────────────────────────────
    if query_type in ("gap", "overlap") and event_name and event_name2:
        rows1 = fetch_by_name(event_name)
        rows2 = fetch_by_name(event_name2)

        if not rows1:
            return [make_chunk(f"No calendar data found for '{event_name}'. Cannot compute gap.")]
        if not rows2:
            return [make_chunk(f"No calendar data found for '{event_name2}'. Cannot compute gap.")]

        _,      end1   = boundary_dates(rows1)
        start2, _      = boundary_dates(rows2)

        chunks = [
            make_chunk(f"'{event_name}' ends on {end1}."),
            make_chunk(f"'{event_name2}' starts on {start2}."),
        ]

        gap_start = (date.fromisoformat(end1) + timedelta(days=1)).isoformat()
        gap_end   = (date.fromisoformat(start2) - timedelta(days=1)).isoformat()

        if gap_start > gap_end:
            chunks.append(make_chunk(
                f"'{event_name}' and '{event_name2}' overlap or are back-to-back — gap is 0 days."
            ))
        else:
            gap_days = count_working_days(gap_start, gap_end)
            chunks.append(make_chunk(
                f"The gap between '{event_name}' and '{event_name2}' is {gap_days} working days "
                f"(excluding Sundays and holidays)."
            ))
        return chunks

    # ─────────────────────────────────────────────────────────────────────────
    # COUNT queries — all derived from DB
    # ─────────────────────────────────────────────────────────────────────────
    if query_type == "count":
        event_type_param = (params.get("event_type") or "").lower().strip()

        # ── Teaching days ─────────────────────────────────────────────────────
        # Teaching days = days from CoC to Last Working Day that are NOT
        # holiday / exam / co_curricular / vacation / registration.
        # 'academic' rows (CoC, Compensatory Working Days, Last Working Day)
        # DO count as teaching days, so we do not exclude them.
        if "teaching" in event_type_param:
            coc_rows = fetch_by_name("Commencement of Classes")
            lwd_rows = fetch_by_name("Last Working Day")

            if not coc_rows or not lwd_rows:
                return [make_chunk(
                    "Cannot determine teaching days: 'Commencement of Classes' "
                    "or 'Last Working Day' not found in the calendar."
                )]

            sem_start = coc_rows[0]["event_date"]
            sem_end   = lwd_rows[-1]["event_date"]

            all_in_range = fetch_in_range(sem_start, sem_end)
            non_teaching_dates = {
                r["event_date"] for r in all_in_range
                if r["event_type"] in ("holiday", "exam", "vacation","co_curricular")
            }

            count = sum(
                1 for d in iter_dates(sem_start, sem_end)
                if d.isoformat() not in non_teaching_dates
            )
            return [make_chunk(
                f"There are {count} teaching days in the even semester "
                f"(from {sem_start} to {sem_end}, inclusive)."
            )]

        # ── Saturday holidays ────────────────────────────────────────────────
        if "saturday" in event_type_param:
            rows  = fetch_by_name("saturday")
            count = len(rows)
            dates = ", ".join(r["event_date"] for r in rows)
            return [make_chunk(
                f"There are {count} Saturday holidays: {dates}."
            )]

        # ── General / named holidays (non-Sunday, non-Saturday) ─────────────
        if "general" in event_type_param:
            all_holidays = fetch_by_type("holiday")
            general = [
                r for r in all_holidays
                if not re.search(r"\b(sunday|saturday)\b", r.get("event_name", ""), re.IGNORECASE)
            ]
            count = len(general)
            names = ", ".join(
                f"{r['event_name']} ({r['event_date']})" for r in general
            )
            return [make_chunk(
                f"There are {count} general/named holidays: {names}."
            )]

        # ── Link holidays ────────────────────────────────────────────────────
        if "link" in event_type_param:
            rows  = fetch_by_name("link holiday")
            count = len(rows)
            dates = ", ".join(
                f"{r['event_name']} ({r['event_date']})" for r in rows
            )
            return [make_chunk(
                f"There are {count} link holidays: {dates}."
            )]

        # ── Compensatory working days ─────────────────────────────────────────
        if "compensatory" in event_type_param:
            rows  = fetch_by_name("compensatory working day")
            count = len(rows)
            dates = ", ".join(
                f"{r['event_name']} ({r['event_date']})" for r in rows
            )
            return [make_chunk(
                f"There are {count} compensatory working days: {dates}."
            )]

        # ── Co-curricular days ───────────────────────────────────────────────
        if "co_curricular" in event_type_param or "co curricular" in event_type_param:
            rows  = fetch_by_type("co_curricular")
            count = len(rows)
            dates = ", ".join(
                f"{r['event_name']} ({r['event_date']})" for r in rows
            )
            return [make_chunk(
                f"There are {count} co-curricular activity days: {dates}."
            )]
        # ─────────────────────────────────────────────────────────────────────────
    # COUNT HOLIDAYS IN A MONTH — count in Python, never let LLM count
    # ─────────────────────────────────────────────────────────────────────────
    if (params.get("month") and 
        params.get("event_type") and 
        "holiday" in params.get("event_type", "").lower() and
        query_type == "count"):
        
        month = params["month"]
        year, mon = month.split("-")
        last_day = cal_module.monthrange(int(year), int(mon))[1]
        
        rows = (
            supabase.table("academic_calendar")
            .select("*")
            .eq("event_type", "holiday")
            .gte("event_date", f"{month}-01")
            .lte("event_date", f"{month}-{last_day:02d}")
            .order("event_date", desc=False)
            .execute()
            .data
        )
        
        count = len(rows)
        names = ", ".join(f"{r['event_name']} ({r['event_date']})" for r in rows)
        month_name = date(int(year), int(mon), 1).strftime("%B %Y")
        
        return [make_chunk(
            f"There are exactly {count} holidays in {month_name}: {names}."
        )]
   
    # ─────────────────────────────────────────────────────────────────────────
    # DEFAULT — delegate to existing query helpers
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # DEFAULT — delegate to existing query helpers
    # ─────────────────────────────────────────────────────────────────────────
    data = query_calendar(params)
    # In retrieve_chunks(), at the very bottom DEFAULT section:

    # ← ADD THIS
    if not data and params.get("is_college_open_query") and params.get("date"):
        return [make_chunk(
            f"There are no holidays or events recorded for {params['date']}. "
            f"College is open as usual on this day."
        )]
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
                email = f["email"]
                if isinstance(email, list):
                    email = ", ".join(email)  # 👈 join both emails
                lines.append(f"Email: {email}")
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
   # Filter by research area — ilike on text array
    # Filter by research area — ilike on text array
    if params.get("research_area"):
        query = query.ilike("areas_of_interest", f"%{params['research_area']}%")
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
