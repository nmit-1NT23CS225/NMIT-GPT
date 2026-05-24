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
        chat_history = [{"role": m.role, "content": m.content} for m in payload.history]
        result = answer_query(payload.question, chat_history=chat_history)
        return result
    except Exception as e:
        import traceback
        print("FULL ERROR:\n", traceback.format_exc())  # 👈 add this line only
        raise HTTPException(status_code=500, detail=str(e))
