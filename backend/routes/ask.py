from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from RAG_ENGINE.src.pipeline import answer_query

router = APIRouter(prefix="/ask", tags=["Ask"])


class Message(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    history: Optional[List[Message]] = []


@router.post("/")
def ask_question(payload: AskRequest):
    try:
        # convert history to list of dicts for the LLM
        chat_history = [{"role": m.role, "content": m.content} for m in payload.history]
        result = answer_query(payload.question, chat_history=chat_history)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))