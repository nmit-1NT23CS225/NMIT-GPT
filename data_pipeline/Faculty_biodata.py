import pandas as pd
from supabase import create_client
from sentence_transformers import SentenceTransformer
from datetime import datetime
from dotenv import load_dotenv
import os
file_path = r"C:\Shini\Nmit GPT Project\project new\Copy of faculty_template_full(1).xlsx"
df = pd.read_excel(file_path)
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MODEL_NAME = os.getenv("EMBEDDING_MODEL")
model = SentenceTransformer(MODEL_NAME)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
def clean_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        try:
            dt = pd.to_datetime(value)
            return str(dt.date())
        except:
            return None
    try:
        return str(value.date())
    except:
        return None
def to_array(value):
    if pd.isna(value):
        return []
    return [v.strip() for v in str(value).split(",")]
for i, row in df.iterrows():
    raw_text = row["raw_text"] if "raw_text" in df.columns else ""
    embedding = model.encode(raw_text).tolist()
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
        "text_data": [raw_text],   
        "embedding": embedding
    }
    supabase.table("faculty_biodata").insert(faculty_data).execute()
print("✅ All faculty biodata uploaded into Supabase successfully!")

