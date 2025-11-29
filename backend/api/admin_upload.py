from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from backend.api.auth import admin_required

router = APIRouter(prefix="/admin", tags=["Admin"])

def process_excel(path: str):
    # TODO: implement parsing, chunking, embedding, inserting into Supabase
    pass

@router.post("/upload/biodata-excel", dependencies=[admin_required()])
async def upload_excel(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    background_tasks.add_task(process_excel, temp_path)
    return {"status": "processing"}
