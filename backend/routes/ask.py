from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from RAG_ENGINE.src.pipeline import answer_query

router = APIRouter(prefix="/ask", tags=["Ask"])

class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

@router.post("/")
def ask_question(payload: AskRequest):
    try:
        result = answer_query(payload.question, payload.top_k)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
