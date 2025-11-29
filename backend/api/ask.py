from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from RAG_ENGINE.src.pipeline import answer_query

router = APIRouter(prefix="/ask", tags=["Ask"])

class AskRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


@router.post("/")
def ask(payload: AskRequest):
    question = payload.query
    result = answer_query(question, payload.top_k)
    return result

