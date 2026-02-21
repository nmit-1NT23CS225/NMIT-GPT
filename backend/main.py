from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.ask import router as ask_router
from backend.routes.faculty import router as faculty_router
from backend.routes.embeddings import router as embeddings_router
from backend.routes.admin_upload import router as admin_router
from backend.routes.debug import router as debug_router
from backend.routes.auth import router as auth_router
from backend.routes.health import router as health_router

app = FastAPI(title="Faculty-GPT Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask_router)
app.include_router(faculty_router)
app.include_router(embeddings_router)
app.include_router(admin_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.include_router(health_router)
