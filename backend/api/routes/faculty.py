from fastapi import APIRouter, HTTPException
from RAG_ENGINE.src.db import get_supabase_client

router = APIRouter(prefix="/faculty", tags=["Faculty"])
supabase = get_supabase_client()

@router.get("/")
def list_faculty():
    resp = supabase.table("faculty_biodata").select("*").execute()
    return resp.data

@router.get("/{faculty_id}")
def get_faculty(faculty_id: str):
    resp = supabase.table("faculty_biodata").select("*").eq("faculty_id", faculty_id).single().execute()
    if resp.error:
        raise HTTPException(status_code=404, detail="Faculty not found")
    return resp.data
