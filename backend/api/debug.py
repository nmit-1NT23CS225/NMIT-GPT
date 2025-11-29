from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from RAG_ENGINE.src.db import get_supabase_client

router = APIRouter(prefix="/debug", tags=["Debug"])
supabase = get_supabase_client()

class RPCMatch(BaseModel):
    embedding: List[float]
    match_count: int = 5

@router.post("/rpc/match")
def debug_match(req: RPCMatch):
    resp = supabase.rpc(
        "match_faculty_chunks",   # ✔ CORRECT RPC NAME
        {
            "query_embedding": req.embedding,
            "match_count": req.match_count
        }
    ).execute()

    if resp.error:
        raise HTTPException(status_code=500, detail=str(resp.error))
    
    return resp.data
