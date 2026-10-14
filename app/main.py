from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import AnalyzerSettings, analyze
from .fitlite import FitDecodeError, decode_activity

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(title="Windsurfing Gybe Analyzer", version="0.3.1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.3.1"}


@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    min_course_change_deg: float = Form(105.0),
    min_entry_speed_kt: float = Form(4.0),
    min_exit_speed_kt: float = Form(1.5),
    planning_threshold_kt: float = Form(8.0),
) -> dict:
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Filen är större än 50 MB")
    if not payload:
        raise HTTPException(status_code=400, detail="Tom fil")

    settings = AnalyzerSettings(
        min_course_change_deg=max(60.0, min(180.0, min_course_change_deg)),
        min_entry_speed_kt=max(0.0, min(40.0, min_entry_speed_kt)),
        min_exit_speed_kt=max(0.0, min(40.0, min_exit_speed_kt)),
        planning_threshold_kt=max(0.0, min(40.0, planning_threshold_kt)),
    )
    try:
        points = decode_activity(payload, file.filename or "activity.fit")
        result = analyze(points, settings)
    except FitDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysen misslyckades: {exc}") from exc

    result["source"] = {"filename": file.filename, "size_bytes": len(payload)}
    return result
