import pandas as pd

def clean_date(value):
    if pd.isna(value):
        return None
    try:
        return str(pd.to_datetime(value).date())
    except:
        return None

def to_array(value):
    if pd.isna(value):
        return []
    return [v.strip() for v in str(value).split(",")]

def extract_faculty_data(file_path):
    df = pd.read_excel(file_path)
    faculty_list = []

    for i, row in df.iterrows():
        raw_text = row["raw_text"] if "raw_text" in df.columns else ""

        faculty_data = {
            "faculty_id": str(i + 1),
            "name": row.get("name"),
            "designation": row.get("designation"),
            "department": row.get("department"),
            "email": to_array(row.get("email")),
            "joining_date": clean_date(row.get("joining_date")),
            "educational_qualifications": to_array(row.get("qualification")),
            "past_experience": to_array(row.get("experience")),
            "areas_of_interest": to_array(row.get("interests")),
            "achievements": to_array(row.get("achievements")),
            "subjects_taught": to_array(row.get("subjects_taught")),
            "scholar_id": to_array(row.get("scholar_id")),
            "orcid_id": to_array(row.get("orcid_id")),
            "linkedin_id": to_array(row.get("linkedIn_id")),
            "research": to_array(row.get("research")),
            "raw_text": [raw_text],   # store as list
        }

        faculty_list.append(faculty_data)

    return faculty_list
