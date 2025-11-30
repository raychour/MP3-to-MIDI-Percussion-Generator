from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import shutil
import os
from app.core import process_audio

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('app/static/index.html')

@app.post("/process")
async def process_endpoint(file: UploadFile = File(...)):
    temp_file = f"temp_{file.filename}"
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        midi_path = process_audio(temp_file)
        return FileResponse(midi_path, filename="output.mid")
    finally:
        # Cleanup temp input file, output file cleanup might need a background task
        if os.path.exists(temp_file):
            os.remove(temp_file)
