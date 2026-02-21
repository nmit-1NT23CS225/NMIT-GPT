from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class LoginRequest(BaseModel):
    username: str
    password: str

def admin_required():
    def verify(token: str = Depends(oauth2_scheme)):
        if token != "fake-admin-token":
            raise HTTPException(status_code=401, detail="Unauthorized")
        return True
    return Depends(verify)

@router.post("/login")
def login(request: LoginRequest):
    if request.username == "admin" and request.password == "admin":
        return {
            "access_token": "fake-admin-token",
            "token_type": "bearer"
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")
