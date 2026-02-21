from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from RAG_ENGINE.src.db import get_supabase_client

router = APIRouter(prefix="/debug", tags=["Debug"])
supabase = get_supabase_client()

class RPCRequest(BaseModel):
    embedding: List[float]
    match_count: int = 5

@router.post("/rpc/match")
def debug_rpc(req: RPCRequest):
    response = supabase.rpc(
        "match_documents",
        {
            "query_embedding": req.embedding,
            "match_count": req.match_count
        }
    ).execute()

    return response.data
