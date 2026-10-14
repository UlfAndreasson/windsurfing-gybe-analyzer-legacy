from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import AnalyzerSettings, analyze
from .fitlite import FitDecodeError, decode_activity

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
SESSIONS_DIR = PROJECT_DIR / "data" / "sessions"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SESSION_ID_RE = re.compile(r"^[0-9a-f]{16}$")
VERSION = "0.5.0"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Windsurfing Gybe Analyzer", version=VERSION)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION}


def _settings(
    min_course_change_deg: float,
    min_entry_speed_kt: float,
    min_exit_speed_kt: float,
    planning_threshold_kt: float,
    wind_from_deg: str | None,
) -> AnalyzerSettings:
    wind: float | None = None
    if wind_from_deg is not None and str(wind_from_deg).strip() != "":
        try:
            wind = float(wind_from_deg) % 360.0
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Vindriktning måste vara grader 0–359") from exc
    return AnalyzerSettings(
        min_course_change_deg=max(60.0, min(180.0, min_course_change_deg)),
        min_entry_speed_kt=max(0.0, min(40.0, min_entry_speed_kt)),
        min_exit_speed_kt=max(0.0, min(40.0, min_exit_speed_kt)),
        planning_threshold_kt=max(0.0, min(40.0, planning_threshold_kt)),
        wind_from_deg=wind,
    )


def _session_dir(session_id: str) -> Path:
    if not SESSION_ID_RE.fullmatch(session_id):
        raise HTTPException(status_code=404, detail="Okänd session")
    path = SESSIONS_DIR / session_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Okänd session")
    return path


def _source_file(path: Path) -> Path:
    matches = sorted(path.glob("source.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Källfilen saknas för sparad session")
    return matches[0]


def _atomic_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def _save_session(payload: bytes, filename: str, result: dict) -> dict:
    session_id = hashlib.sha256(payload).hexdigest()[:16]
    folder = SESSIONS_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)
    suffix = ".zip" if filename.lower().endswith(".zip") else ".fit"

    for old in folder.glob("source.*"):
        if old.suffix.lower() != suffix:
            old.unlink(missing_ok=True)
    (folder / f"source{suffix}").write_bytes(payload)

    saved_at = datetime.now(timezone.utc).isoformat()
    result["session_id"] = session_id
    result["saved_at_utc"] = saved_at
    result["source"] = {"filename": filename, "size_bytes": len(payload)}
    _atomic_json(folder / "analysis.json", result)
    return result


def _run(payload: bytes, filename: str, settings: AnalyzerSettings) -> dict:
    try:
        points = decode_activity(payload, filename)
        result = analyze(points, settings)
    except FitDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysen misslyckades: {exc}") from exc
    return _save_session(payload, filename, result)


@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    min_course_change_deg: float = Form(105.0),
    min_entry_speed_kt: float = Form(4.0),
    min_exit_speed_kt: float = Form(1.5),
    planning_threshold_kt: float = Form(8.0),
    wind_from_deg: str | None = Form(None),
) -> dict:
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Filen är större än 50 MB")
    if not payload:
        raise HTTPException(status_code=400, detail="Tom fil")
    filename = file.filename or "activity.fit"
    return _run(
        payload,
        filename,
        _settings(min_course_change_deg, min_entry_speed_kt, min_exit_speed_kt, planning_threshold_kt, wind_from_deg),
    )


@app.get("/api/sessions")
def list_sessions() -> dict:
    sessions: list[dict] = []
    for folder in SESSIONS_DIR.iterdir():
        if not folder.is_dir() or not SESSION_ID_RE.fullmatch(folder.name):
            continue
        analysis_file = folder / "analysis.json"
        if not analysis_file.exists():
            continue
        try:
            saved = json.loads(analysis_file.read_text(encoding="utf-8"))
            sessions.append(
                {
                    "session_id": folder.name,
                    "saved_at_utc": saved.get("saved_at_utc"),
                    "source": saved.get("source", {}),
                    "summary": saved.get("summary", {}),
                    "settings": saved.get("settings", {}),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    sessions.sort(key=lambda item: item.get("summary", {}).get("start_utc", ""), reverse=True)
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    folder = _session_dir(session_id)
    try:
        return json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sparad analys saknas") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Sparad analys är skadad") from exc


@app.post("/api/sessions/{session_id}/reanalyze")
def reanalyze_session(
    session_id: str,
    min_course_change_deg: float = Form(105.0),
    min_entry_speed_kt: float = Form(4.0),
    min_exit_speed_kt: float = Form(1.5),
    planning_threshold_kt: float = Form(8.0),
    wind_from_deg: str | None = Form(None),
) -> dict:
    folder = _session_dir(session_id)
    source = _source_file(folder)
    payload = source.read_bytes()
    old = get_session(session_id)
    filename = old.get("source", {}).get("filename") or source.name
    return _run(
        payload,
        filename,
        _settings(min_course_change_deg, min_entry_speed_kt, min_exit_speed_kt, planning_threshold_kt, wind_from_deg),
    )
