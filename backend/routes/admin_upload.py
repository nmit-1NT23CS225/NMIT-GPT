from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from backend.routes.auth import admin_required

router = APIRouter(prefix="/admin", tags=["Admin"])

def process_excel(file_path: str):
    pass

@router.post("/upload/biodata-excel", dependencies=[admin_required()])
async def upload_excel(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    file_path = f"/tmp/{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    background_tasks.add_task(process_excel, file_path)

    return {"status": "processing"}
