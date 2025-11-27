import os
from dotenv import load_dotenv
from supabase import create_client
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase configuration")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_faculty(faculty_data):
    supabase.table("faculty_biodata").insert(faculty_data).execute()

def fetch_all_faculty():
    return supabase.table("faculty_biodata").select("faculty_id, raw_text").execute().data
