from fastapi import APIRouter, HTTPException
from RAG_ENGINE.src.db import get_supabase_client

router = APIRouter(prefix="/embeddings", tags=["Embeddings"])
supabase = get_supabase_client()

@router.get("/by-faculty/{faculty_id}")
def get_embeddings(faculty_id: str):
    resp = supabase.table("faculty_biodata_embeddings").select("*").eq("faculty_id", faculty_id).execute()
    return resp.data
        