from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uuid
from typing import Dict
from app.core import process_audio

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# In-memory task store
# Structure: { task_id: { "status": "processing"|"complete"|"error", "progress": int, "message": str, "tempo": float, "result": str } }
tasks: Dict[str, dict] = {}

def run_processing_task(task_id: str, temp_file: str, quantization: int):
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = "Starting..."
        
        def progress_callback(progress: int, message: str):
            tasks[task_id]["progress"] = progress
            tasks[task_id]["message"] = message

        midi_path, tempo = process_audio(temp_file, progress_callback, quantization)
        
        tasks[task_id]["status"] = "complete"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "Complete"
        tasks[task_id]["tempo"] = tempo
        tasks[task_id]["result"] = midi_path
        
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["message"] = str(e)
    finally:
        # Cleanup input file
        if os.path.exists(temp_file):
            os.remove(temp_file)

@app.get("/")
async def read_index():
    return FileResponse('app/static/index.html')

@app.post("/process")
def process_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...), quantization: int = 16):
    task_id = str(uuid.uuid4())
    temp_file = f"temp_{task_id}_{file.filename}"
    
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "tempo": 0.0,
        "result": None
    }
    
    background_tasks.add_task(run_processing_task, task_id, temp_file, quantization)
    
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/download/{task_id}")
async def download_result(task_id: str):
    if task_id not in tasks or tasks[task_id]["status"] != "complete":
        raise HTTPException(status_code=404, detail="Result not ready or found")
    
    return FileResponse(tasks[task_id]["result"], filename="output.mid")
