from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.ask import router as ask_router
from backend.api.faculty import router as faculty_router
from backend.api.embeddings import router as embeddings_router
from backend.api.admin_upload import router as admin_upload_router
from backend.api.debug import router as debug_router
from backend.api.auth import router as auth_router
from backend.api.health import router as health_router

app = FastAPI(title="Faculty-GPT API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask_router)
app.include_router(faculty_router)
app.include_router(embeddings_router)
app.include_router(admin_upload_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.include_router(health_router)
