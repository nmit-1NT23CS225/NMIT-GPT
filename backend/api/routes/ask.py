from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from RAG_ENGINE.src.pipeline import answer_query

router = APIRouter(prefix="/ask", tags=["Ask"])

class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

@router.post("/")
def ask_question(payload: AskRequest):
    result = answer_query(payload.question, payload.top_k)
    return result
