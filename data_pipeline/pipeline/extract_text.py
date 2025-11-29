import pandas as pd
import datetime

def clean_date(value):
    if pd.isna(value) or value == "":
        return None
    try:
        return str(pd.to_datetime(value).date())
    except:
        return None

def to_array(value):
    if pd.isna(value) or value == "":
        return []
    return [v.strip() for v in str(value).split(",")]

def extract_faculty_data(filepath):
    df = pd.read_excel(filepath)
    faculty_list = []

    for index, row in df.iterrows():

        faculty_data = {
            "faculty_id": index + 1,                         
            "name": row.get("name", ""),
            "designation": row.get("designation", ""),
            "department": row.get("department", ""),

            "email": to_array(row.get("email")),
            "educational_qualifications": to_array(row.get("qualification")),
            "past_experience": to_array(row.get("experience")),
            "areas_of_interest": to_array(row.get("interests")),
            "subjects_taught": to_array(row.get("subjects_taught")),
            "achievements": to_array(row.get("achievements")),
            "scholar_id": to_array(row.get("scholar_id")),
            "orcid_id": to_array(row.get("orcid_id")),
            "linkedin_id": to_array(row.get("linkedIn_id")),
            "research": to_array(row.get("research")),

            "joining_date": clean_date(row.get("joining_date")),

            "raw_text": ""  
        }

        faculty_list.append(faculty_data)

    return faculty_list
