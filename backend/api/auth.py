from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

def admin_required():
    def verify():
        return True
    return Depends(verify)

@router.post("/login")
def login(req: LoginRequest):
    if req.username == "admin" and req.password == "admin":
        return {"token": "fake-admin-token"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
