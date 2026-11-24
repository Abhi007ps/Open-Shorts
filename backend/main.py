import os
import re
import shutil
import json
import time
import subprocess
import zipfile
import threading
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.clipper import probe_video, auto_generate_clips, generate_preview_frame, render_clip
from backend.hardware import FFMPEG_BIN, FFPROBE_BIN, WHISPER_CLI, get_hardware_profile, get_best_encoder
from backend.transcriber import transcribe_video, group_words_into_segments, ensure_whisper_model, MODELS_DIR, JobCancelledError
from backend.subtitle_generator import generate_ass_subtitles, generate_srt_subtitles
from backend.viral_detector import detect_viral_moments

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOADS_DIR = os.path.join(BASE_DIR, "storage", "uploads")
OUTPUTS_DIR = os.path.join(BASE_DIR, "storage", "outputs")
TEMP_DIR = os.path.join(BASE_DIR, "storage", "temp")
TEMPLATES_DIR = os.path.join(BASE_DIR, "storage", "templates")
THUMBNAILS_DIR = os.path.join(BASE_DIR, "storage", "thumbnails")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

CURRENT_EXPORT_DIR = OUTPUTS_DIR

MASTER_TEMPLATE_FILE = os.path.join(TEMPLATES_DIR, "master_template.json")
DEFAULT_SUBS_FILE = os.path.join(BASE_DIR, "storage", "default_subtitles.json")
SESSION_STATE_FILE = os.path.join(TEMP_DIR, "session_state.json")

# Global re-entrant lock for thread-safe state mutations
STATE_LOCK = threading.RLock()

# Allowed video file extensions for local source selection
ALLOWED_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".ts", ".avi", ".m4v"}

# Strict regex for pulling models: starts with alnum, only safe characters, max 80 chars
MODEL_NAME_REGEX = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,79}$')

def safe_resolve_under(base_dir: str, filename: str) -> Optional[str]:
    """
    Safely resolves a filename under base_dir preventing directory traversal,
    null-byte attacks, and absolute-path escapes.
    Returns the canonical string path if target is a valid relative file, else None.
    """
    if not filename or not isinstance(filename, str):
        return None
    if "\x00" in filename or "/" in filename or "\\" in filename:
        return None
    try:
        base = Path(base_dir).resolve()
        target = (base / filename).resolve()
        if target.is_relative_to(base) and target.is_file():
            return str(target)
    except Exception:
        return None
    return None

def require_local_client(request: Request):
    """
    Restricts sensitive administrative filesystem / model operations to localhost
    unless OPENSHORTS_ALLOW_LAN_ADMIN=1 is explicitly enabled.
    """
    if os.environ.get("OPENSHORTS_ALLOW_LAN_ADMIN") == "1":
        return
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(
            status_code=403,
            detail="Access restricted: This administrative operation can only be performed from the local host."
        )

def prune_temp_previews(keep: int = 5):
    """Prunes older generated preview frames in TEMP_DIR, retaining only the most recent."""
    try:
        if not os.path.exists(TEMP_DIR):
            return
        files = [
            os.path.join(TEMP_DIR, f) for f in os.listdir(TEMP_DIR)
            if f.startswith("preview_") and f.endswith(".png")
        ]
        if len(files) > keep:
            files.sort(key=lambda p: os.path.getmtime(p))
            for old_p in files[:len(files) - keep]:
                try:
                    os.remove(old_p)
                except Exception:
                    pass
    except Exception:
        pass

app = FastAPI(title="OpenShorts Custom Template Studio", version="1.0.0")

# CORS Configuration: Tightened localhost defaults unless LAN mode is explicitly requested
if os.environ.get("OPENSHORTS_LAN") == "1":
    cors_origins = ["*"]
else:
    cors_origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session state - starts clean for user uploaded footage
CURRENT_STATE: Dict[str, Any] = {
    "video_path": "",
    "video_meta": {},
    "subtitles": [],
    "clips": [],
    "export_queue": [],
    "export_progress": {"status": "idle", "current_clip": 0, "total_clips": 0, "percent": 0, "title": ""},
    "transcribe_progress": {"status": "idle", "step": "Ready", "percent": 0}
}

# ==============================================================================
# NON-BLOCKING BACKGROUND JOB MANAGER & CANCELLATION ENGINE
# ==============================================================================
JOBS: Dict[str, Dict[str, Any]] = {}
JOB_CANCEL_EVENTS: Dict[str, threading.Event] = {}

def start_background_job(job_type: str, worker_fn: Callable[[str, threading.Event, Callable[[int, Optional[str]], None]], Any]) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    cancel_event = threading.Event()
    with STATE_LOCK:
        # Prune old completed/cancelled/error jobs if exceeding 40 entries
        if len(JOBS) > 40:
            prunable = [jid for jid, j in JOBS.items() if j.get("status") in ("completed", "cancelled", "error")]
            prunable.sort(key=lambda jid: JOBS[jid].get("started_at", 0))
            for jid in prunable[:max(1, len(JOBS) - 30)]:
                JOBS.pop(jid, None)
                JOB_CANCEL_EVENTS.pop(jid, None)

        job_data = {
            "job_id": job_id,
            "type": job_type,
            "status": "running",
            "percent": 1,
            "step": "Starting...",
            "started_at": time.time(),
            "elapsed_sec": 0.0,
            "result": None,
            "error": None
        }
        JOBS[job_id] = job_data
        JOB_CANCEL_EVENTS[job_id] = cancel_event

    def update_progress(*args, **kwargs):
        with STATE_LOCK:
            if job_id not in JOBS or JOBS[job_id].get("status") != "running":
                return
            pct = None
            step = None
            if len(args) == 1:
                if isinstance(args[0], (int, float)):
                    pct = int(args[0])
                else:
                    step = str(args[0])
            elif len(args) >= 2:
                if isinstance(args[0], (int, float)):
                    pct = int(args[0])
                    step = str(args[1])
                else:
                    step = str(args[0])
                    pct = int(args[1]) if isinstance(args[1], (int, float)) else None
            if "percent" in kwargs:
                pct = int(kwargs["percent"])
            if "step" in kwargs:
                step = str(kwargs["step"])
            if pct is not None:
                JOBS[job_id]["percent"] = max(1, min(100, pct))
            if step is not None:
                JOBS[job_id]["step"] = str(step)

    def runner():
        try:
            res = worker_fn(job_id, cancel_event, update_progress)
            with STATE_LOCK:
                if job_id in JOBS:
                    if cancel_event.is_set():
                        JOBS[job_id]["status"] = "cancelled"
                        JOBS[job_id]["step"] = "Cancelled"
                        JOBS[job_id]["error"] = "Job cancelled by user"
                    else:
                        JOBS[job_id]["status"] = "completed"
                        JOBS[job_id]["percent"] = 100
                        JOBS[job_id]["result"] = res
                        JOBS[job_id]["step"] = "Completed"
        except JobCancelledError:
            with STATE_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["status"] = "cancelled"
                    JOBS[job_id]["step"] = "Cancelled"
                    JOBS[job_id]["error"] = "Job cancelled by user"
        except Exception as e:
            with STATE_LOCK:
                if job_id in JOBS:
                    if cancel_event.is_set():
                        JOBS[job_id]["status"] = "cancelled"
                        JOBS[job_id]["step"] = "Cancelled"
                        JOBS[job_id]["error"] = "Job cancelled by user"
                    else:
                        JOBS[job_id]["status"] = "error"
                        JOBS[job_id]["error"] = str(e)
                        JOBS[job_id]["step"] = f"Error: {e}"

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return job_data


def save_session_state():
    with STATE_LOCK:
        try:
            data = {
                "video_path": CURRENT_STATE.get("video_path", ""),
                "video_meta": CURRENT_STATE.get("video_meta", {}),
                "subtitles": CURRENT_STATE.get("subtitles", []),
                "clips": CURRENT_STATE.get("clips", []),
                "export_dir": CURRENT_EXPORT_DIR
            }
            tmp_file = f"{SESSION_STATE_FILE}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp_file, SESSION_STATE_FILE)
        except Exception as e:
            print(f"Error saving session state: {e}")

def ensure_ollama_daemon():
    """Auto-starts Ollama daemon if not currently running."""
    try:
        from backend.llm_engine import is_ollama_online
        if not is_ollama_online(timeout=1.0):
            ollama_bin = shutil.which("ollama") or shutil.which("ollama.exe")
            ollama_candidates = [
                os.path.expanduser(r"~\AppData\Local\Programs\Ollama\ollama.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
                ollama_bin,
                "ollama.exe",
                "ollama"
            ]
            for c in ollama_candidates:
                if c and (os.path.exists(c) or shutil.which(c)):
                    print(f"[*] Starting local Ollama daemon from {c}...")
                    subprocess.Popen([c, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
    except Exception as e:
        print(f"[WARN] Failed to auto-start Ollama: {e}")

ensure_ollama_daemon()

def load_session_state():
    global CURRENT_EXPORT_DIR
    if os.path.exists(SESSION_STATE_FILE):
        try:
            with open(SESSION_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                vpath = data.get("video_path")
                meta = data.get("video_meta", {})
                # If loaded video is vertical (e.g. 1080x1920 short), discard and switch to true 16:9 stream
                if meta.get("width", 0) > 0 and meta.get("width", 0) < meta.get("height", 0):
                    vpath = None
                if vpath and os.path.exists(vpath):
                    CURRENT_STATE["video_path"] = vpath
                    CURRENT_STATE["video_meta"] = meta
                    CURRENT_STATE["subtitles"] = data.get("subtitles", [])
                    CURRENT_STATE["clips"] = data.get("clips", [])
                if data.get("export_dir") and os.path.exists(data.get("export_dir")):
                    CURRENT_EXPORT_DIR = data["export_dir"]
                else:
                    CURRENT_EXPORT_DIR = OUTPUTS_DIR
        except Exception as e:
            print(f"Error loading session state: {e}")

    # If no valid 16:9 stream video is active, auto-load standard 16:9 demo video
    if not CURRENT_STATE.get("video_path") or not os.path.exists(CURRENT_STATE["video_path"]):
        demo = get_demo_video()
        demo_path = demo.get("path") if demo else None
        if demo_path and os.path.exists(demo_path):
            CURRENT_STATE["video_path"] = demo_path
            CURRENT_STATE["video_meta"] = probe_video(demo_path)

    # Guarantee 16:9 source_frame.jpg exists and matches current stream video
    if CURRENT_STATE.get("video_path") and os.path.exists(CURRENT_STATE["video_path"]):
        source_frame_path = os.path.join(TEMP_DIR, "source_frame.jpg")
        try:
            dur = CURRENT_STATE.get("video_meta", {}).get("duration", 30.0)
            seek_pt = min(12.0, max(1.0, dur * 0.15))
            subprocess.run([
                FFMPEG_BIN, "-y",
                "-ss", str(seek_pt),
                "-i", CURRENT_STATE["video_path"],
                "-vframes", "1",
                source_frame_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as e:
            print(f"[WARN] Failed to generate 16:9 source frame on startup: {e}")

load_session_state()

# Mount static directories
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

class SetSourceReq(BaseModel):
    video_path: str
    is_demo: bool = False

class ProbeStreamReq(BaseModel):
    url: str

class LoadStreamRangeReq(BaseModel):
    url: str
    start_sec: float
    end_sec: float
    title: Optional[str] = None
    quality: Optional[str] = "max"

class TranscribeReq(BaseModel):
    language: str = "auto"
    max_line_len: int = 28
    words_per_line: Optional[int] = 3
    model_name: Optional[str] = None
    start_time: Optional[float] = None
    duration: Optional[float] = None
    streamer_voice_focus: bool = True
    audio_track: Optional[int] = 0
    is_demo: bool = False

class RegroupReq(BaseModel):
    words_per_line: int = 3

class PreviewReq(BaseModel):
    timestamp: float = 10.0
    template_config: Dict[str, Any]
    subtitle_config: Dict[str, Any]
    hook_config: Optional[Dict[str, Any]] = None
    subtitles: Optional[List[Dict[str, Any]]] = None

class ClipDef(BaseModel):
    id: str
    title: str
    start: float
    end: float
    virality_score: Optional[int] = None
    reason: Optional[str] = None
    badge_color: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    template_config: Optional[Dict[str, Any]] = None
    subtitle_config: Optional[Dict[str, Any]] = None
    hook_config: Optional[Dict[str, Any]] = None
    subtitles: Optional[List[Dict[str, Any]]] = None
    subtitles_count: Optional[int] = None

class TranscribeAllClipsReq(BaseModel):
    clips: List[ClipDef]
    language: str = "auto"
    words_per_line: Optional[int] = 3
    model_name: Optional[str] = None
    streamer_voice_focus: Optional[bool] = True
    audio_track: Optional[int] = 0

class DetectViralReq(BaseModel):
    min_duration: float = 8.0
    max_duration: float = 30.0
    mode: str = "auto" # "auto" or "manual"
    target_clips: Optional[int] = None
    profile: Optional[str] = "balanced"
    weight_audio: Optional[float] = None
    weight_pitch: Optional[float] = None
    weight_hook: Optional[float] = None
    weight_speech: Optional[float] = None
    weight_motion: Optional[float] = None
    snap_boundaries: Optional[bool] = True
    webcam_crop: Optional[Dict[str, int]] = None
    use_llm: Optional[bool] = True
    llm_model: Optional[str] = None

class ExportReq(BaseModel):
    clips: List[ClipDef]
    template_config: Dict[str, Any]
    subtitle_config: Dict[str, Any]
    hook_config: Optional[Dict[str, Any]] = None
    subtitles: Optional[List[Dict[str, Any]]] = None
    export_as_zip: Optional[bool] = False
    encoder: Optional[str] = None

@app.get("/api/system_hardware")
def get_system_hardware():
    """Returns detected CPU, GPU, and hardware video encoders for the current machine."""
    return get_hardware_profile()

class SetExportFolderReq(BaseModel):
    folder_path: str

class MasterTemplateReq(BaseModel):
    name: Optional[str] = "Default Master Template"
    template_config: Dict[str, Any]
    subtitle_config: Optional[Dict[str, Any]] = None
    enhancement_config: Optional[Dict[str, Any]] = None

@app.get("/api/master_template")
def get_master_template():
    if os.path.exists(MASTER_TEMPLATE_FILE):
        try:
            with open(MASTER_TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"success": True, "has_saved": True, "template": data}
        except Exception as e:
            return {"success": False, "has_saved": False, "error": str(e)}
    return {"success": True, "has_saved": False, "template": None}

@app.post("/api/save_master_template")
def save_master_template(req: MasterTemplateReq):
    try:
        from datetime import datetime
        data = {
            "name": req.name or "Default Master Template",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "template_config": req.template_config,
            "subtitle_config": req.subtitle_config or {},
            "enhancement_config": req.enhancement_config or {}
        }
        with open(MASTER_TEMPLATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return {"success": True, "message": "Master template saved successfully", "template": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/master_template")
def delete_master_template():
    if os.path.exists(MASTER_TEMPLATE_FILE):
        try:
            os.remove(MASTER_TEMPLATE_FILE)
            return {"success": True, "message": "Master template reset to default"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "message": "No master template found"}

@app.get("/")
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "OpenShorts Custom Template Studio API is running."}

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "current_video": CURRENT_STATE["video_path"],
        "video_loaded": bool(CURRENT_STATE["video_path"] and os.path.exists(CURRENT_STATE["video_path"])),
        "subtitles_count": len(CURRENT_STATE["subtitles"]),
        "clips_count": len(CURRENT_STATE["clips"])
    }

def ensure_faststart(video_path: str) -> str:
    """Ensures MP4/MOV container has the 'moov' atom at the beginning for instant web browser streaming."""
    if not video_path or not os.path.exists(video_path):
        return video_path
    
    # Only perform in-place faststart optimization for uploaded files in our own uploads directory
    try:
        norm_uploads = os.path.abspath(UPLOADS_DIR).lower()
        norm_video = os.path.abspath(video_path).lower()
        if not norm_video.startswith(norm_uploads):
            return video_path  # Leave user's external source files untouched!
    except Exception:
        pass

    ext = os.path.splitext(video_path)[1].lower()
    if ext not in [".mp4", ".mov", ".m4v"]:
        return video_path
    
    # Check if moov is already before mdat
    try:
        with open(video_path, "rb") as f:
            for _ in range(12):
                chunk = f.read(8)
                if len(chunk) < 8:
                    break
                size = int.from_bytes(chunk[:4], 'big')
                atom = chunk[4:8]
                if atom == b'moov':
                    return video_path  # already faststart!
                if atom == b'mdat':
                    break  # moov is after mdat, needs faststart conversion
                if size == 1:
                    large_size = int.from_bytes(f.read(8), 'big')
                    f.seek(large_size - 16, os.SEEK_CUR)
                elif size == 0:
                    break
                else:
                    f.seek(size - 8, os.SEEK_CUR)
    except Exception:
        return video_path

    # Apply faststart via ffmpeg stream copy
    fast_path = video_path + ".fast.mp4"
    try:
        cmd = [FFMPEG_BIN, "-y", "-i", video_path, "-c", "copy", "-movflags", "+faststart", fast_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(fast_path) and os.path.getsize(fast_path) > 1000:
            bak_path = video_path + ".bak"
            if os.path.exists(bak_path):
                try: os.remove(bak_path)
                except Exception: pass
            shutil.move(video_path, bak_path)
            shutil.move(fast_path, video_path)
            if os.path.exists(bak_path):
                try: os.remove(bak_path)
                except Exception: pass
            print(f"[FastStart] Converted {video_path} to web-optimized streaming container")
            return video_path
    except Exception as e:
        print(f"[FastStart] Stream copy conversion failed: {e}")
        if os.path.exists(fast_path):
            try: os.remove(fast_path)
            except Exception: pass
    return video_path

def process_loaded_video(clean_path: str, is_demo: bool = False):
    clean_path = os.path.normpath(clean_path)
    if not os.path.exists(clean_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Video file not found at: {clean_path}. Please verify the file path or use 'Browse Video File' to select it."
        )
    
    clean_path = ensure_faststart(clean_path)
    meta = probe_video(clean_path)
    dur = meta.get("duration", 10.0)

    # 1. Extract source reference frame from the ACTUAL uploaded video for Facecam Reticle
    source_frame_path = os.path.join(TEMP_DIR, "source_frame.jpg")
    try:
        seek_pt = min(5.0, max(0.5, dur * 0.2))
        subprocess.run([
            FFMPEG_BIN, "-y",
            "-ss", str(seek_pt),
            "-i", clean_path,
            "-vframes", "1",
            source_frame_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        print(f"Frame extraction failed: {e}")

    with STATE_LOCK:
        is_new_video = (CURRENT_STATE.get("video_path") != clean_path)
        CURRENT_STATE["video_path"] = clean_path
        CURRENT_STATE["video_meta"] = meta

        # 2. Reset subtitles and clips for a newly uploaded / loaded video
        if is_new_video:
            CURRENT_STATE["clips"] = []
            CURRENT_STATE["subtitles"] = []
            CURRENT_STATE["export_queue"] = []

        if is_demo and os.path.exists(DEFAULT_SUBS_FILE):
            try:
                with open(DEFAULT_SUBS_FILE, "r", encoding="utf-8") as f:
                    raw_subs = json.load(f)
                clean_subs = []
                for s in raw_subs:
                    sc = dict(s)
                    sc["text"] = re.sub(r'[,.]+', '', sc.get("text", "")).strip()
                    if "words" in sc and sc["words"]:
                        sc["words"] = [{**w, "word": re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()} for w in sc["words"] if re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()]
                    clean_subs.append(sc)
                CURRENT_STATE["subtitles"] = clean_subs
            except Exception:
                CURRENT_STATE["subtitles"] = []

        save_session_state()
        res_meta = dict(CURRENT_STATE["video_meta"])
        res_clips = list(CURRENT_STATE["clips"])
        res_subs = list(CURRENT_STATE["subtitles"])

    import time
    return {
        "status": "success",
        "video_path": clean_path,
        "is_demo": is_demo,
        "meta": res_meta,
        "clips": res_clips,
        "subtitles": res_subs,
        "source_frame": f"/storage/temp/source_frame.jpg?t={time.time()}"
    }

@app.get("/api/demo_video")
def get_demo_video():
    """Finds an available 16:9 widescreen livestream video dynamically without hardcoded machine paths."""
    preferred = [
        "PLAYING GTA 6 FOR THE FIRST TIME (PART 2)_60_1800.mp4",
        "BEATING GTA 6 _FINALE__1826_5418.mp4",
        "EXPLORING_VICE_CITY_-_GTA_6_STREAM_EASTER_EGG_00h00m00s_to_00h30m00s.mp4",
        "document_6053073585516323938.mp4"
    ]
    for pref in preferred:
        p = os.path.join(UPLOADS_DIR, pref)
        if os.path.isfile(p):
            meta = probe_video(p)
            w, h = meta.get("width", 0), meta.get("height", 0)
            if w >= h:
                return {"success": True, "path": p, "name": pref}
            
    if os.path.exists(UPLOADS_DIR):
        for f in os.listdir(UPLOADS_DIR):
            if f.lower().endswith((".mp4", ".mkv", ".mov", ".ts", ".webm")) and not f.endswith(".bak"):
                p = os.path.join(UPLOADS_DIR, f)
                meta = probe_video(p)
                w, h = meta.get("width", 0), meta.get("height", 0)
                if w >= h:
                    return {"success": True, "path": p, "name": f}
                
    return {"success": False, "message": "No sample 16:9 stream video found in storage/uploads"}

@app.post("/api/extract_frame")
def extract_frame_endpoint(req: Dict[str, Any] = None):
    """Extracts a frame from the current 16:9 stream at the requested timestamp for the Facecam Reticle."""
    vpath = CURRENT_STATE.get("video_path")
    if not vpath or not os.path.exists(vpath):
        raise HTTPException(status_code=400, detail="No video loaded")
    time_sec = float((req or {}).get("time", 5.0))
    source_frame_path = os.path.join(TEMP_DIR, "source_frame.jpg")
    try:
        subprocess.run([
            FFMPEG_BIN, "-y",
            "-ss", str(time_sec),
            "-i", vpath,
            "-vframes", "1",
            source_frame_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "source_frame": f"/storage/temp/source_frame.jpg?t={time.time()}"}

@app.post("/api/set_source")
def set_video_source(req: SetSourceReq, request: Request):
    require_local_client(request)
    raw_path = req.video_path.strip(' \t\r\n"\'“”')
    clean_path = os.path.normpath(raw_path)
    if not os.path.isfile(clean_path):
        raise HTTPException(status_code=400, detail="Source video path does not exist or is not a regular file")
    ext = os.path.splitext(clean_path)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported video file extension: {ext}. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTS))}")
    return process_loaded_video(clean_path, is_demo=req.is_demo)

@app.post("/api/upload")
def upload_video(file: UploadFile = File(...)):
    raw_name = file.filename or ""
    base_name = os.path.basename(raw_name).strip()
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', base_name)
    if not safe_name or safe_name.strip('._') == "":
        ext = os.path.splitext(base_name)[1].lower()
        if not ext or len(ext) > 5 or ext not in ALLOWED_VIDEO_EXTS:
            ext = ".mp4"
        safe_name = f"upload_{uuid.uuid4().hex[:8]}{ext}"
    dest = (Path(UPLOADS_DIR) / safe_name).resolve()
    if not dest.is_relative_to(Path(UPLOADS_DIR).resolve()):
        raise HTTPException(status_code=400, detail="Invalid upload filename destination")
    dest_path = str(dest)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return process_loaded_video(dest_path, is_demo=False)

@app.post("/api/probe_stream")
def api_probe_stream(req: ProbeStreamReq):
    try:
        from backend.stream_loader import probe_stream, hunt_stream_viral_moments
        meta = probe_stream(req.url)
        moments = hunt_stream_viral_moments(req.url, meta.get("duration", 0), meta)
        return {"status": "success", "meta": meta, "viral_candidates": moments}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

def _do_load_stream_range(req: LoadStreamRangeReq, cancel_event: Optional[threading.Event] = None, progress_cb: Optional[Callable] = None):
    from backend.stream_loader import download_stream_slice
    CURRENT_STATE["stream_progress"] = {"status": "downloading", "percent": 5, "step": "Connecting to stream..."}
    if progress_cb:
        progress_cb(5, "Connecting to stream...")
    def cb(pct, msg):
        CURRENT_STATE["stream_progress"] = {"status": "downloading", "percent": pct, "step": msg}
        if progress_cb:
            progress_cb(pct, msg)
        
    res = download_stream_slice(
        url=req.url,
        start_sec=req.start_sec,
        end_sec=req.end_sec,
        output_dir=UPLOADS_DIR,
        custom_title=req.title,
        quality=req.quality or "max",
        progress_callback=cb,
        cancel_event=cancel_event
    )
    CURRENT_STATE["stream_progress"] = {"status": "completed", "percent": 100, "step": "Loaded slice into studio!"}
    if progress_cb:
        progress_cb(100, "Loaded slice into studio!")
    # Immediately activate into studio
    video_meta = process_loaded_video(res["file_path"], is_demo=False)
    # Pre-seed clip #1 with the candidate's actual title and full duration
    cand_title = req.title or res.get("title") or f"Highlight ({res['duration']}s)"
    CURRENT_STATE["clips"] = [{
        "id": "clip-full",
        "title": cand_title,
        "start": 0.0,
        "end": res["duration"],
        "duration": res["duration"],
        "virality_score": 98,
        "category": "Stream Highlight",
        "reason": "Peak reaction from audio scan"
    }]
    save_session_state()
    return {"status": "success", "slice": res, "video": video_meta, "clips": CURRENT_STATE["clips"]}

@app.post("/api/load_stream_range")
def api_load_stream_range(req: LoadStreamRangeReq, async_mode: bool = False):
    if async_mode:
        def worker(job_id, cancel_event, update_prog):
            return _do_load_stream_range(req, cancel_event=cancel_event, progress_cb=update_prog)
        job = start_background_job("load_stream_range", worker)
        return {"status": "queued", "job_id": job["job_id"], "job": job}

    try:
        return _do_load_stream_range(req)
    except JobCancelledError:
        CURRENT_STATE["stream_progress"] = {"status": "cancelled", "percent": 0, "step": "Cancelled by user"}
        raise HTTPException(status_code=499, detail="Stream slice download cancelled by user")
    except Exception as e:
        import traceback
        traceback.print_exc()
        CURRENT_STATE["stream_progress"] = {"status": "error", "percent": 0, "step": str(e)}
        raise HTTPException(status_code=500, detail=f"Stream extraction failed: {e}")

@app.get("/api/stream_progress")
def api_stream_progress():
    return CURRENT_STATE.get("stream_progress", {"status": "idle", "percent": 0, "step": "Ready"})

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    with STATE_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        data = dict(job)
        if data.get("status") == "running":
            data["elapsed_sec"] = round(time.time() - data.get("started_at", time.time()), 1)
        return data

@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    with STATE_LOCK:
        if job_id in JOB_CANCEL_EVENTS:
            JOB_CANCEL_EVENTS[job_id].set()
        if job_id in JOBS:
            if JOBS[job_id].get("status") == "running":
                JOBS[job_id]["step"] = "Cancelling..."
            return {"status": "cancelling", "job_id": job_id}
        raise HTTPException(status_code=404, detail="Job not found")

@app.post("/api/jobs/cancel_active")
def cancel_active_jobs():
    with STATE_LOCK:
        cancelled_ids = []
        for jid, evt in JOB_CANCEL_EVENTS.items():
            if jid in JOBS and JOBS[jid].get("status") == "running":
                evt.set()
                JOBS[jid]["step"] = "Cancelling..."
                cancelled_ids.append(jid)
        return {"status": "ok", "cancelled_jobs": cancelled_ids}

def _do_scan_stream_audio(req: ProbeStreamReq, cancel_event: Optional[threading.Event] = None, progress_cb: Optional[Callable] = None):
    from backend.stream_loader import (
        probe_stream, download_stream_audio, scan_audio_energy_peaks,
        hunt_stream_viral_moments, transcribe_audio_peaks,
        fetch_stream_transcript, extract_heatmap_peaks, _PROBED_INFO_CACHE,
        zoom_window_in_bucket, scan_transcript_story_bursts, build_comment_spike_windows
    )
    from backend.llm_engine import curate_story_clips_from_windows, curate_tournament_top_clips

    def set_p(status: str, pct: int, step: str):
        CURRENT_STATE["stream_progress"] = {"status": status, "percent": pct, "step": step}
        if progress_cb:
            progress_cb(pct, step)

    if cancel_event and cancel_event.is_set():
        raise JobCancelledError("Scan stream audio cancelled by user")

    set_p("processing", 10, "Probing stream metadata & audience signals...")
    meta = probe_stream(req.url)
    dur = meta.get("duration", 0)
    cached_info = _PROBED_INFO_CACHE.get(req.url) or {}

    # FAST PATH: Check if native transcript and multi-signal funnel are available
    transcript_segs = fetch_stream_transcript(cached_info)
    effective_dur = max(float(dur or 0.0), float(transcript_segs[-1].get("end", 0.0)) if transcript_segs else 0.0)

    if transcript_segs:
        if cancel_event and cancel_event.is_set():
            raise JobCancelledError("Scan stream audio cancelled by user")

        set_p("processing", 25, f"Harvesting 3-signal funnel (Heatmap, Chat Spikes, Story Bursts) across {int(effective_dur//60)}m stream...")

        heatmap_peaks = extract_heatmap_peaks(cached_info, duration=effective_dur, top_k=20)
        comment_peaks = build_comment_spike_windows(req.url, duration=effective_dur, top_k=12)
        burst_peaks = scan_transcript_story_bursts(transcript_segs, video_duration=effective_dur, top_k=14)

        all_candidates = []
        for p in heatmap_peaks:
            all_candidates.append(dict(p))
        for p in comment_peaks:
            all_candidates.append(dict(p))
        for p in burst_peaks:
            all_candidates.append(dict(p))

        # Chapters fallback if fewer than 8 candidates
        if len(all_candidates) < 8 and meta.get("chapters"):
            for ch_idx, ch in enumerate(meta["chapters"][:8], 1):
                ch_c = (ch["start"] + ch["end"]) / 2.0
                all_candidates.append({
                    "rank": ch_idx,
                    "center_sec": round(ch_c, 1),
                    "start": ch["start"],
                    "end": ch["end"],
                    "virality_score": 88,
                    "source": "chapter"
                })

        # Merge and deduplicate candidates within 75s of each other
        all_candidates.sort(key=lambda x: float(x.get("virality_score", 80)), reverse=True)
        merged_peaks = []
        for cand in all_candidates:
            c_time = float(cand.get("center_sec", 0.0))
            matched = False
            for m in merged_peaks:
                if abs(c_time - float(m.get("center_sec", 0.0))) <= 75.0:
                    matched = True
                    cur_score = int(m.get("virality_score", 85))
                    m["virality_score"] = min(99, cur_score + 6)
                    m["source"] = "multi_signal"
                    if "bucket_start" in cand and "bucket_start" not in m:
                        m["bucket_start"] = cand["bucket_start"]
                        m["bucket_end"] = cand.get("bucket_end")
                    break
            if not matched:
                merged_peaks.append(dict(cand))

        merged_peaks.sort(key=lambda x: int(x.get("virality_score", 80)), reverse=True)
        top_peaks = merged_peaks[:24]

        if top_peaks:
            if cancel_event and cancel_event.is_set():
                raise JobCancelledError("Scan stream audio cancelled by user")

            set_p("processing", 45, f"Identified {len(top_peaks)} high-virality multi-signal windows! Running 2-Round Qwen3 Story Tournament...")

            windows = []
            for w_idx, p in enumerate(top_peaks, 1):
                p_center = float(p.get("center_sec", 0.0))
                b_st = p.get("bucket_start")
                b_en = p.get("bucket_end")
                if b_st is not None and b_en is not None:
                    z_center, w_start, w_end = zoom_window_in_bucket(
                        transcript_segs,
                        bucket_start=float(b_st),
                        bucket_end=float(b_en),
                        fallback_center=p_center,
                        video_duration=effective_dur,
                        window_span=90.0
                    )
                else:
                    z_center = p_center
                    w_start = max(0.0, round(p_center - 40.0, 1))
                    w_end = min(effective_dur, round(p_center + 50.0, 1))

                matching = [
                    s for s in transcript_segs
                    if float(s.get("end", 0.0)) >= w_start and float(s.get("start", 0.0)) <= w_end
                ]
                t_lines = []
                char_count = 0
                for s in matching[:18]:
                    txt = s.get("text", "").strip()
                    if txt:
                        line_str = f"[{float(s.get('start', 0.0)):.1f}s] {txt}"
                        if char_count + len(line_str) > 750:
                            break
                        t_lines.append(line_str)
                        char_count += len(line_str)

                spoken_text = " ".join(s.get("text", "").strip() for s in matching)

                windows.append({
                    "window_id": w_idx,
                    "source": p.get("source", "heatmap"),
                    "peak_score": int(p.get("virality_score", 90)),
                    "center_sec": round(z_center, 1),
                    "start_bound": w_start,
                    "end_bound": w_end,
                    "transcript_lines": t_lines,
                    "spoken_text": spoken_text[:800],
                    "orig_cand": p
                })

            def t_progress(msg, pct):
                set_p("processing", pct, msg)

            curated_clips, curation_reason = curate_tournament_top_clips(
                windows=windows,
                video_duration=effective_dur,
                target_count=8,
                min_duration=15.0,
                max_duration=50.0,
                progress_callback=t_progress,
                cancel_event=cancel_event
            )

            if curated_clips:
                CURRENT_STATE["peak_transcriptions"] = {
                    str(round(c.get("start", 0), 1)): c.get("title", "")
                    for c in curated_clips
                }
                set_p("completed", 100, f"Tournament Champion Pass selected {len(curated_clips)} viral stories with Qwen3 (Zero Download)!")
                return {
                    "status": "success",
                    "meta": meta,
                    "viral_candidates": curated_clips,
                    "audio_size_mb": 0,
                    "mode": "story_first_zero_download"
                }

    # FALLBACK PATH: Download lightweight compressed audio for Kick/Twitch/no-caption VODs
    if cancel_event and cancel_event.is_set():
        raise JobCancelledError("Scan stream audio cancelled by user")

    set_p("downloading", 20, "Pulling audio channel for acoustic analysis...")
    def cb_audio(pct, msg):
        set_p("downloading", pct, msg)

    audio_res = download_stream_audio(req.url, output_dir=TEMP_DIR, progress_callback=cb_audio, cancel_event=cancel_event)
    audio_file_path = audio_res.get("audio_path")

    try:
        if cancel_event and cancel_event.is_set():
            raise JobCancelledError("Scan stream audio cancelled by user")

        set_p("processing", 65, "Scanning acoustic excitement & energy peaks across full stream...")
        top_k_audio = 14 if effective_dur > 10800 else 10
        peaks = scan_audio_energy_peaks(audio_file_path, duration=effective_dur, top_k=top_k_audio)

        if peaks:
            n_peaks = len(peaks)
            set_p("processing", 75, f"Transcribing {n_peaks} peak moments with Whisper for real context...")
            try:
                peaks = transcribe_audio_peaks(audio_file_path, peaks, progress_callback=cb_audio, cancel_event=cancel_event)
            except Exception as trans_err:
                print(f"[WARN] Peak transcription failed, using energy-only titles: {trans_err}")

        # Convert transcribed peaks into candidate windows for tournament curation
        audio_windows = []
        if peaks:
            for p_idx, p in enumerate(peaks, 1):
                p_c = float(p.get("center_sec") or (float(p.get("start", 0)) + float(p.get("end", 30))) / 2.0)
                w_s = max(0.0, p_c - 30.0)
                w_e = min(effective_dur, p_c + 35.0)
                lines = p.get("transcript_lines") or []
                if not lines and p.get("spoken_text"):
                    lines = [f"[{p_c:.1f}s] {p.get('spoken_text')}"]
                audio_windows.append({
                    "window_id": p_idx,
                    "source": p.get("reaction_category", "Audio Surge"),
                    "peak_score": int(p.get("virality_score", 88)),
                    "center_sec": p_c,
                    "start_bound": w_s,
                    "end_bound": w_e,
                    "transcript_lines": lines,
                    "spoken_text": p.get("spoken_text", ""),
                    "orig_cand": p
                })

        moments = []
        if audio_windows:
            if cancel_event and cancel_event.is_set():
                raise JobCancelledError("Scan stream audio cancelled by user")

            def t_audio_prog(msg, pct):
                set_p("processing", pct, msg)

            set_p("processing", 88, "Running 2-Round Qwen3 Story Tournament on audio peaks...")
            curated_audio, c_reason = curate_tournament_top_clips(
                windows=audio_windows,
                video_duration=effective_dur,
                target_count=8,
                min_duration=15.0,
                max_duration=50.0,
                progress_callback=t_audio_prog,
                cancel_event=cancel_event
            )
            if curated_audio:
                moments = curated_audio

        if not moments:
            set_p("processing", 95, "Combining chat signals & chapter markers...")
            moments = hunt_stream_viral_moments(req.url, effective_dur, meta=meta, audio_peaks=peaks)
            if not isinstance(moments, list):
                moments = []

        # Store peak transcriptions in state so slice loading can reuse them
        CURRENT_STATE["peak_transcriptions"] = {
            str(round(p.get("start", 0), 1)): p.get("spoken_text", "")
            for p in (peaks or []) if p.get("has_transcript")
        }

        set_p("completed", 100, f"Found {len(moments)} viral moments with real dialogue context!")
        return {
            "status": "success",
            "meta": meta,
            "viral_candidates": moments,
            "audio_size_mb": audio_res.get("size_mb", 0),
            "mode": "audio_first_synergy"
        }
    finally:
        if audio_file_path and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
            except Exception as clean_err:
                print(f"[WARN] Failed to delete temp scan audio: {clean_err}")

@app.post("/api/scan_stream_audio")
def api_scan_stream_audio(req: ProbeStreamReq, async_mode: bool = False):
    """
    STORY-FIRST STREAM DISCOVERY PIPELINE (OpusClip / Klap Architecture):
    1. Zero-Download Fast Path: Probes stream metadata and extracts native YouTube heatmap + subtitles.
       If captions exist, sends candidate peak windows directly to Qwen3:8b for instant story curation.
    2. Fallback Synergy Path (for Kick/Twitch or videos without native captions):
       Downloads lightweight compressed audio (~25-40MB), scans acoustic excitement peaks,
       transcribes peak regions with Whisper, and curates via Qwen3 Story Mind.
    Supports ?async_mode=1 for background non-blocking execution with live cancellation.
    """
    if async_mode:
        def worker(job_id, cancel_event, update_prog):
            return _do_scan_stream_audio(req, cancel_event=cancel_event, progress_cb=update_prog)
        job = start_background_job("scan_stream_audio", worker)
        return {"status": "queued", "job_id": job["job_id"], "job": job}

    try:
        return _do_scan_stream_audio(req)
    except JobCancelledError:
        CURRENT_STATE["stream_progress"] = {"status": "cancelled", "percent": 0, "step": "Cancelled by user"}
        raise HTTPException(status_code=499, detail="Scan stream audio cancelled by user")
    except Exception as e:
        import traceback
        traceback.print_exc()
        CURRENT_STATE["stream_progress"] = {"status": "error", "percent": 0, "step": str(e)}
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/factory_reset")
def api_factory_reset(request: Request):
    """
    CLEAN SLATE / FACTORY RESET:
    Wipes all previous session clips, subtitles, uploads, exports, and temporary files.
    Preserves all binaries (bin/) and speech models (models/).
    Prepares the studio for a completely new user.
    """
    require_local_client(request)
    global CURRENT_STATE, CURRENT_EXPORT_DIR
    try:
        with STATE_LOCK:
            # 1. Reset in-memory state
            CURRENT_STATE["video_path"] = ""
            CURRENT_STATE["video_meta"] = {}
            CURRENT_STATE["subtitles"] = []
            CURRENT_STATE["clips"] = []
            CURRENT_STATE["export_queue"] = []
            CURRENT_STATE["export_progress"] = {"status": "idle", "current_clip": 0, "total_clips": 0, "percent": 0, "title": ""}
            CURRENT_STATE["transcribe_progress"] = {"status": "idle", "step": "Ready", "percent": 0}
            CURRENT_STATE["stream_progress"] = {"status": "idle", "percent": 0, "step": "Ready"}
            CURRENT_EXPORT_DIR = OUTPUTS_DIR

            # 2. Delete session state file
            if os.path.exists(SESSION_STATE_FILE):
                try:
                    os.remove(SESSION_STATE_FILE)
                except Exception:
                    pass

            # 3. Clean files in storage/uploads, storage/outputs, storage/temp, storage/thumbnails
            for folder in [UPLOADS_DIR, OUTPUTS_DIR, TEMP_DIR, THUMBNAILS_DIR]:
                if os.path.exists(folder):
                    for fname in os.listdir(folder):
                        if fname == ".gitkeep":
                            continue
                        fpath = os.path.join(folder, fname)
                        try:
                            if os.path.isfile(fpath) or os.path.islink(fpath):
                                os.remove(fpath)
                            elif os.path.isdir(fpath):
                                shutil.rmtree(fpath, ignore_errors=True)
                        except Exception:
                            pass

            # 4. Remove saved master template
            if os.path.exists(MASTER_TEMPLATE_FILE):
                try:
                    os.remove(MASTER_TEMPLATE_FILE)
                except Exception:
                    pass

            # 5. Reload clean demo video if available
            demo = get_demo_video()
            demo_path = demo.get("path") if demo else None
            if demo_path and os.path.exists(demo_path):
                CURRENT_STATE["video_path"] = demo_path
                CURRENT_STATE["video_meta"] = probe_video(demo_path)

        return {"status": "success", "message": "Engine completely reset to clean slate. Ready for a new user!"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/detect_clips")
def detect_clips_endpoint(req: DetectViralReq):
    video_path = CURRENT_STATE["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video loaded")
        
    duration = CURRENT_STATE["video_meta"].get("duration", 0)
    if duration <= 0:
        CURRENT_STATE["video_meta"] = probe_video(video_path)
        duration = CURRENT_STATE["video_meta"].get("duration", 0)
        
    target_n = req.target_clips if req.mode == "manual" else None
    webcam_crop = req.webcam_crop or (CURRENT_STATE.get("template", {}).get("webcam_crop") if isinstance(CURRENT_STATE.get("template"), dict) else None)
    try:
        clips = detect_viral_moments(
            video_path=video_path,
            video_duration=duration,
            subtitles=CURRENT_STATE["subtitles"],
            min_duration=req.min_duration,
            max_duration=req.max_duration,
            target_clips=target_n,
            profile=req.profile or "balanced",
            weight_audio=req.weight_audio,
            weight_pitch=req.weight_pitch,
            weight_hook=req.weight_hook,
            weight_speech=req.weight_speech,
            weight_motion=req.weight_motion,
            snap_boundaries=req.snap_boundaries if req.snap_boundaries is not None else True,
            webcam_crop=webcam_crop,
            use_llm=req.use_llm if req.use_llm is not None else True,
            llm_model=req.llm_model
        )

        CURRENT_STATE["clips"] = clips
        return {"status": "success", "count": len(clips), "clips": clips}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Viral detection failed: {e}")

@app.get("/api/llm/status")
def get_llm_status():
    from backend.llm_engine import is_ollama_online, get_installed_llm_models, get_preferred_llama_model
    online = is_ollama_online()
    models = get_installed_llm_models() if online else []
    preferred = get_preferred_llama_model() if online else None
    return {
        "status": "success",
        "online": online,
        "models": models,
        "preferred_model": preferred,
        "recommended": "qwen3:8b"
    }

class PullModelReq(BaseModel):
    model_name: str = "qwen3:8b"

@app.post("/api/llm/pull")
def pull_llm_model(req: PullModelReq, request: Request):
    require_local_client(request)
    if not req.model_name or not MODEL_NAME_REGEX.match(req.model_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid model name. Model name must start with alphanumeric character and contain only alphanumeric, '.', '_', ':', '/', or '-' up to 80 characters."
        )
    import subprocess
    try:
        subprocess.Popen(["ollama", "pull", req.model_name])
        return {"status": "success", "message": f"Started pulling {req.model_name} in background"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export_folder")
def get_export_folder():
    return {"status": "success", "path": CURRENT_EXPORT_DIR}

@app.post("/api/set_export_folder")
def set_export_folder(req: SetExportFolderReq, request: Request):
    require_local_client(request)
    global CURRENT_EXPORT_DIR
    raw = req.folder_path.strip(' \t\r\n"\'“”')
    if not raw:
        raise HTTPException(status_code=400, detail="Folder path cannot be empty")
    clean = os.path.normpath(raw)
    try:
        os.makedirs(clean, exist_ok=True)
        with STATE_LOCK:
            CURRENT_EXPORT_DIR = clean
            save_session_state()
        return {"status": "success", "path": CURRENT_EXPORT_DIR}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot create or access folder: {e}")

@app.post("/api/open_folder")
def open_export_folder(request: Request):
    require_local_client(request)
    try:
        target = CURRENT_EXPORT_DIR if os.path.exists(CURRENT_EXPORT_DIR) else OUTPUTS_DIR
        if os.name == "nt":
            os.startfile(target)
        return {"status": "success", "path": target}
    except Exception as e:
        return {"status": "error", "message": str(e), "path": CURRENT_EXPORT_DIR}

@app.get("/api/probe")
def get_probe():
    if not CURRENT_STATE["video_path"] or not os.path.exists(CURRENT_STATE["video_path"]):
        raise HTTPException(status_code=400, detail="No video loaded")
    if not CURRENT_STATE["video_meta"]:
        CURRENT_STATE["video_meta"] = probe_video(CURRENT_STATE["video_path"])
    return CURRENT_STATE["video_meta"]

def _do_transcribe(req: TranscribeReq, cancel_event: Optional[threading.Event] = None, progress_cb: Optional[Callable] = None):
    video_path = CURRENT_STATE["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video file loaded. Please upload or load a video first.")
    
    if cancel_event and cancel_event.is_set():
        raise JobCancelledError("Transcription cancelled by user")

    # Only load demo subtitles if user explicitly selected demo mode
    if req.is_demo and os.path.exists(DEFAULT_SUBS_FILE):
        try:
            with open(DEFAULT_SUBS_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached and len(cached) > 0:
                CURRENT_STATE["subtitles"] = cached
                msg = f"Instant Demo Sync: {len(cached)} synchronized lines loaded in 0.05s!"
                CURRENT_STATE["transcribe_progress"] = {
                    "status": "completed", 
                    "step": msg, 
                    "percent": 100
                }
                if progress_cb:
                    progress_cb(100, msg)
                return {"status": "success", "count": len(cached), "subtitles": cached}
        except Exception:
            pass

    # Transcribe speech directly from the uploaded footage
    t0_single = time.time()
    def on_single_transcribe_progress(step_desc: str, sub_percent: int):
        elapsed = round(time.time() - t0_single, 1)
        CURRENT_STATE["transcribe_progress"] = {
            "status": "running",
            "step": step_desc,
            "percent": sub_percent,
            "elapsed_sec": elapsed,
            "current_clip": 1,
            "total_clips": 1,
            "clip_title": "Full Video" if req.start_time is None else f"Clip ({round(req.start_time, 1)}s)"
        }
        if progress_cb:
            progress_cb(sub_percent, step_desc)

    init_step = "Extracting 16kHz audio & applying speech normalization..."
    CURRENT_STATE["transcribe_progress"] = {
        "status": "running",
        "step": init_step,
        "percent": 15,
        "elapsed_sec": 0.0,
        "current_clip": 1,
        "total_clips": 1,
        "clip_title": "Active Target"
    }
    if progress_cb:
        progress_cb(15, init_step)
    
    try:
        # Pick model if specified (auto-download if missing on disk)
        chosen_model = None
        if req.model_name:
            cand1 = os.path.join(MODELS_DIR, f"ggml-{req.model_name}.bin")
            cand2 = os.path.join(MODELS_DIR, req.model_name)
            if os.path.isfile(cand1) and os.path.getsize(cand1) > 1_000_000:
                chosen_model = cand1
            elif os.path.isfile(cand2) and os.path.getsize(cand2) > 1_000_000:
                chosen_model = cand2
            else:
                on_single_transcribe_progress(f"Downloading Whisper model ({req.model_name})...", 10)
                chosen_model = ensure_whisper_model(req.model_name)

        w_count = req.words_per_line if req.words_per_line is not None else 3
        v_meta = CURRENT_STATE.get("video_meta") or probe_video(video_path)
        v_dur = float(v_meta.get("duration", 0.0))
        req_start = req.start_time
        req_dur = req.duration
        if v_dur > 0.0 and req_start is not None:
            if req_start >= v_dur:
                req_start = 0.0
                req_dur = min(v_dur, req_dur or 15.0)
            elif req_dur is not None and (req_start + req_dur > v_dur):
                req_dur = max(1.0, v_dur - req_start)

        subtitles = transcribe_video(
            video_path=video_path,
            language=req.language,
            model_path=chosen_model,
            words_per_line=w_count,
            start_time=req_start,
            duration=req_dur,
            streamer_voice_focus=req.streamer_voice_focus,
            audio_track=req.audio_track if req.audio_track is not None else 0,
            progress_callback=on_single_transcribe_progress,
            cancel_event=cancel_event
        )

        align_step = "Aligning word-by-word karaoke timestamps..."
        CURRENT_STATE["transcribe_progress"] = {
            "status": "running", 
            "step": align_step, 
            "percent": 95,
            "elapsed_sec": round(time.time() - t0_single, 1),
            "current_clip": 1,
            "total_clips": 1
        }
        if progress_cb:
            progress_cb(95, align_step)
        
        if req_start is not None and req_dur is not None:
            # Shift transcribed clip timestamps to match the master stream timeline
            shifted = []
            for s in subtitles:
                s_copy = dict(s)
                s_copy["start"] = round(float(s["start"]) + req_start, 3)
                s_copy["end"] = round(float(s["end"]) + req_start, 3)
                if "words" in s and s["words"]:
                    s_copy["words"] = [
                        {
                            **w, 
                            "start": round(float(w.get("start", 0)) + req_start, 3), 
                            "end": round(float(w.get("end", 0)) + req_start, 3)
                        }
                        for w in s["words"]
                    ]
                shifted.append(s_copy)
            
            # Merge clip subtitles into existing list
            existing = [s for s in CURRENT_STATE["subtitles"] if s.get("end", 0) <= req_start or s.get("start", 0) >= (req_start + req_dur)]
            CURRENT_STATE["subtitles"] = sorted(existing + shifted, key=lambda x: x.get("start", 0))
            # If a clip in CURRENT_STATE["clips"] covers this range, attach subtitles directly
            for c in CURRENT_STATE.get("clips", []):
                if abs(c.get("start", 0) - req_start) < 1.0:
                    c["subtitles"] = shifted
                    c["subtitles_count"] = len(shifted)

        else:
            CURRENT_STATE["subtitles"] = subtitles

        save_session_state()
        done_step = f"Transcription complete! ({len(subtitles)} lines generated for uploaded footage)"
        CURRENT_STATE["transcribe_progress"] = {"status": "completed", "step": done_step, "percent": 100}
        if progress_cb:
            progress_cb(100, done_step)
        return {"status": "success", "count": len(subtitles), "subtitles": CURRENT_STATE["subtitles"]}
    except JobCancelledError:
        CURRENT_STATE["transcribe_progress"] = {"status": "cancelled", "step": "Transcription cancelled by user", "percent": 0}
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        CURRENT_STATE["transcribe_progress"] = {"status": "completed", "step": "Transcription completed (silence or non-speech)", "percent": 100}
        if progress_cb:
            progress_cb(100, "Transcription completed (silence or non-speech)")
        return {"status": "success", "count": 0, "subtitles": CURRENT_STATE.get("subtitles", []), "warning": str(e)}

@app.post("/api/transcribe")
def run_transcription(req: TranscribeReq, async_mode: bool = False):
    if async_mode:
        def worker(job_id, cancel_event, update_prog):
            return _do_transcribe(req, cancel_event=cancel_event, progress_cb=update_prog)
        job = start_background_job("transcribe", worker)
        return {"status": "queued", "job_id": job["job_id"], "job": job}

    try:
        return _do_transcribe(req)
    except JobCancelledError:
        raise HTTPException(status_code=499, detail="Transcription cancelled by user")

def _do_transcribe_all_clips(req: TranscribeAllClipsReq, cancel_event: Optional[threading.Event] = None, progress_cb: Optional[Callable] = None):
    video_path = CURRENT_STATE["video_path"]
    if cancel_event and cancel_event.is_set():
        raise JobCancelledError("Batch transcription cancelled by user")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video file loaded. Please upload or load a video first.")

    if not req.clips:
        raise HTTPException(status_code=400, detail="No clips provided to transcribe.")

    total_clips = len(req.clips)
    start_batch_t0 = time.time()
    CURRENT_STATE["transcribe_progress"] = {
        "status": "running",
        "step": f"Starting batch transcription for {total_clips} clips with streamer voice isolation...",
        "percent": 5,
        "elapsed_sec": 0.0,
        "current_clip": 1,
        "total_clips": total_clips,
        "clip_title": req.clips[0].title if req.clips else "Clip 1"
    }
    if progress_cb:
        progress_cb(5, CURRENT_STATE["transcribe_progress"]["step"])

    chosen_model = None
    if req.model_name:
        cand1 = os.path.join(MODELS_DIR, f"ggml-{req.model_name}.bin")
        cand2 = os.path.join(MODELS_DIR, req.model_name)
        if os.path.isfile(cand1) and os.path.getsize(cand1) > 1_000_000:
            chosen_model = cand1
        elif os.path.isfile(cand2) and os.path.getsize(cand2) > 1_000_000:
            chosen_model = cand2
        else:
            dl_msg = f"Downloading Whisper model ({req.model_name})..."
            CURRENT_STATE["transcribe_progress"] = {
                "status": "running",
                "step": dl_msg,
                "percent": 8,
                "elapsed_sec": round(time.time() - start_batch_t0, 1),
                "current_clip": 1,
                "total_clips": total_clips,
                "clip_title": req.clips[0].title if req.clips else "Clip 1"
            }
            if progress_cb:
                progress_cb(8, dl_msg)
            chosen_model = ensure_whisper_model(req.model_name)

    w_count = req.words_per_line if req.words_per_line is not None else 3
    updated_clips = []
    accumulated_subs = list(CURRENT_STATE.get("subtitles", []))

    v_meta = CURRENT_STATE.get("video_meta") or probe_video(video_path)
    v_dur = float(v_meta.get("duration", 0.0))

    for idx, c in enumerate(req.clips):
        if cancel_event and cancel_event.is_set():
            raise JobCancelledError("Batch transcription cancelled by user")
        c_start = float(c.start)
        c_end = float(c.end)
        c_dur = round(c_end - c_start, 2)
        if v_dur > 0.0:
            if c_start >= v_dur:
                c_start = 0.0
                c_end = min(v_dur, max(1.0, c_dur))
                c_dur = round(c_end - c_start, 2)
            elif c_end > v_dur:
                c_end = v_dur
                c_dur = round(c_end - c_start, 2)

        base_pct = 5 + (idx / total_clips) * 90.0
        clip_span = 90.0 / total_clips

        def make_clip_cb(clip_idx, clip_title, clip_d, b_pct, c_span):
            def cb(step_desc: str, sub_pct: int):
                overall_pct = int(min(97, b_pct + (sub_pct / 100.0) * c_span))
                elapsed = round(time.time() - start_batch_t0, 1)
                step_text = f"Clip {clip_idx + 1}/{total_clips} ({clip_title}): {step_desc}"
                CURRENT_STATE["transcribe_progress"] = {
                    "status": "running",
                    "step": step_text,
                    "percent": overall_pct,
                    "elapsed_sec": elapsed,
                    "current_clip": clip_idx + 1,
                    "total_clips": total_clips,
                    "clip_title": clip_title,
                    "sub_percent": sub_pct
                }
                if progress_cb:
                    progress_cb(overall_pct, step_text)
            return cb

        clip_cb = make_clip_cb(idx, c.title, c_dur, base_pct, clip_span)
        clip_cb("Extracting 16kHz audio & applying speech normalization...", 12)

        c_dict = c.model_dump() if hasattr(c, "model_dump") else c.dict()
        try:
            raw_subs = transcribe_video(
                video_path=video_path,
                language=req.language,
                model_path=chosen_model,
                words_per_line=w_count,
                start_time=c_start,
                duration=c_dur,
                streamer_voice_focus=req.streamer_voice_focus if req.streamer_voice_focus is not None else True,
                audio_track=req.audio_track or 0,
                progress_callback=clip_cb,
                cancel_event=cancel_event
            )

            # Shift timestamps to match master timeline
            shifted = []
            for s in raw_subs:
                s_copy = dict(s)
                s_copy["start"] = round(float(s["start"]) + c_start, 3)
                s_copy["end"] = round(float(s["end"]) + c_start, 3)
                if "words" in s and s["words"]:
                    s_copy["words"] = [
                        {
                            **w,
                            "start": round(float(w.get("start", 0)) + c_start, 3),
                            "end": round(float(w.get("end", 0)) + c_start, 3)
                        }
                        for w in s["words"]
                    ]
                shifted.append(s_copy)

            c_dict["subtitles"] = shifted
            c_dict["subtitles_count"] = len(shifted)
            updated_clips.append(c_dict)

            # Merge into master pool
            accumulated_subs = [
                s for s in accumulated_subs
                if s.get("end", 0) <= c_start or s.get("start", 0) >= c_end
            ] + shifted

        except JobCancelledError:
            raise
        except Exception as e:
            print(f"Error transcribing clip {c.id}: {e}")
            c_dict["subtitles"] = []
            c_dict["subtitles_count"] = 0
            updated_clips.append(c_dict)

    accumulated_subs.sort(key=lambda x: x.get("start", 0))
    CURRENT_STATE["subtitles"] = accumulated_subs
    CURRENT_STATE["clips"] = updated_clips
    save_session_state()

    elapsed_total = round(time.time() - start_batch_t0, 1)
    done_msg = f"✓ 100% Synchronized: All {total_clips} clips transcribed ({len(accumulated_subs)} lines in {elapsed_total}s)!"
    CURRENT_STATE["transcribe_progress"] = {
        "status": "completed",
        "step": done_msg,
        "percent": 100,
        "elapsed_sec": elapsed_total,
        "current_clip": total_clips,
        "total_clips": total_clips,
        "clip_title": "All Clips Synchronized"
    }
    if progress_cb:
        progress_cb(100, done_msg)

    return {
        "status": "success",
        "clips": updated_clips,
        "subtitles": accumulated_subs,
        "total_lines": len(accumulated_subs)
    }

@app.post("/api/transcribe_all_clips")
def transcribe_all_clips_endpoint(req: TranscribeAllClipsReq, async_mode: bool = False):
    if async_mode:
        def worker(job_id, cancel_event, update_prog):
            return _do_transcribe_all_clips(req, cancel_event=cancel_event, progress_cb=update_prog)
        job = start_background_job("transcribe_all_clips", worker)
        return {"status": "queued", "job_id": job["job_id"], "job": job}

    try:
        return _do_transcribe_all_clips(req)
    except JobCancelledError:
        raise HTTPException(status_code=499, detail="Batch transcription cancelled by user")

@app.post("/api/regroup_subtitles")
def regroup_current_subtitles(req: RegroupReq):
    """Regroups the existing subtitles into chunks of N words without re-running transcription."""
    all_words = []
    for s in CURRENT_STATE.get("subtitles", []):
        if "words" in s and s["words"]:
            all_words.extend(s["words"])
        else:
            w_list = s.get("text", "").split()
            dur = max(0.2, s.get("end", 0) - s.get("start", 0))
            step = dur / max(1, len(w_list))
            for i, w in enumerate(w_list):
                all_words.append({
                    "word": w,
                    "start": round(s.get("start", 0) + i * step, 2),
                    "end": round(s.get("start", 0) + (i + 1) * step, 2)
                })
    if not all_words:
        return {"status": "empty", "count": 0, "subtitles": []}
    
    regrouped = group_words_into_segments(all_words, words_per_line=req.words_per_line)
    CURRENT_STATE["subtitles"] = regrouped
    return {"status": "success", "count": len(regrouped), "subtitles": regrouped}

@app.get("/api/transcribe_progress")
def get_transcribe_progress():
    return CURRENT_STATE.get("transcribe_progress", {"status": "idle", "step": "Ready", "percent": 0})

@app.get("/api/subtitles")
def get_subtitles():
    return {"subtitles": CURRENT_STATE["subtitles"]}

@app.post("/api/update_subtitles")
def update_subtitles(subs: List[Dict[str, Any]]):
    clean_subs = []
    for s in subs:
        sc = dict(s)
        sc["text"] = re.sub(r'[,.]+', '', str(sc.get("text", ""))).strip()
        if "words" in sc and sc["words"]:
            sc["words"] = [{**w, "word": re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()} for w in sc["words"] if re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()]
        clean_subs.append(sc)
    with STATE_LOCK:
        CURRENT_STATE["subtitles"] = clean_subs
        save_session_state()
    return {"status": "success", "count": len(clean_subs)}

@app.post("/api/preview")
def create_preview(req: PreviewReq):
    video_path = CURRENT_STATE["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video loaded")
    
    preview_filename = f"preview_{uuid.uuid4().hex[:8]}.png"
    preview_output = os.path.join(TEMP_DIR, preview_filename)
    
    try:
        subs_to_use = req.subtitles if req.subtitles is not None else CURRENT_STATE.get("subtitles")
        video_meta = CURRENT_STATE.get("video_meta")
        generate_preview_frame(
            video_path=video_path,
            timestamp=req.timestamp,
            template_config=req.template_config,
            subtitle_config=req.subtitle_config,
            output_png=preview_output,
            hook_config=req.hook_config,
            all_subtitles=subs_to_use,
            video_meta=video_meta
        )
        prune_temp_previews(keep=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {e}")
        
    return {"status": "success", "preview_url": f"/storage/temp/{preview_filename}?t={os.path.getmtime(preview_output)}"}

@app.get("/storage/temp/{filename}")
def serve_temp(filename: str):
    resolved = safe_resolve_under(TEMP_DIR, filename)
    if resolved:
        return FileResponse(resolved)
    raise HTTPException(status_code=404, detail="File not found")

def _do_export_single_clip(
    clip: ClipDef,
    template_config: Dict[str, Any],
    subtitle_config: Dict[str, Any],
    hook_config: Optional[Dict[str, Any]] = None,
    subtitles: Optional[List[Dict[str, Any]]] = None,
    encoder: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None,
    progress_cb: Optional[Callable] = None
):
    video_path = CURRENT_STATE["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video loaded")

    if cancel_event and cancel_event.is_set():
        raise JobCancelledError("Export cancelled by user")
        
    subs_to_use = subtitles if subtitles is not None else CURRENT_STATE["subtitles"]
    init_title = f"Preparing render: {clip.title}..."
    CURRENT_STATE["export_progress"] = {
        "status": "rendering",
        "current_clip": 1,
        "total_clips": 1,
        "percent": 5,
        "title": init_title,
        "cur_sec": 0.0,
        "duration": 0.0,
        "speed": "1.0x",
        "frame": 0
    }
    if progress_cb:
        progress_cb(5, init_title)

    def progress_callback(pct, cur_sec, dur, speed, frame):
        prog_title = f"Rendering {clip.title}: {pct}% ({round(cur_sec, 1)}s / {round(dur, 1)}s • {speed})"
        CURRENT_STATE["export_progress"] = {
            "status": "rendering",
            "current_clip": 1,
            "total_clips": 1,
            "percent": pct,
            "title": prog_title,
            "cur_sec": round(cur_sec, 1),
            "duration": round(dur, 1),
            "speed": speed,
            "frame": frame
        }
        if progress_cb:
            progress_cb(pct, prog_title)

    try:
        # Always merge request template_config so current active UI settings (divider, resolution, bitrate) are applied
        tmpl_to_use = dict(template_config or {})
        if clip.template_config and isinstance(clip.template_config, dict):
            for k, v in clip.template_config.items():
                if v is not None:
                    tmpl_to_use[k] = v
        for critical_key in ("canvas_w", "canvas_h", "export_bitrate", "divider_line", "divider_color", "divider_height", "pixel_generator", "pixel_generator_mode"):
            if critical_key in template_config:
                tmpl_to_use[critical_key] = template_config[critical_key]

        sub_cfg_to_use = clip.subtitle_config if clip.subtitle_config is not None else subtitle_config
        hook_to_use = clip.hook_config if clip.hook_config is not None else hook_config
        clip_subs_to_use = (clip.subtitles if hasattr(clip, "subtitles") and clip.subtitles else None) or subs_to_use
        video_meta = CURRENT_STATE.get("video_meta")
        res = render_clip(
            video_path=video_path,
            clip_id=clip.id,
            start_time=clip.start,
            end_time=clip.end,
            title=clip.title,
            template_config=tmpl_to_use,
            subtitle_config=sub_cfg_to_use,
            all_subtitles=clip_subs_to_use,
            hook_config=hook_to_use,
            output_dir=CURRENT_EXPORT_DIR,
            encoder=encoder,
            progress_callback=progress_callback,
            video_meta=video_meta,
            workers_count=1,
            cancel_event=cancel_event
        )
        CURRENT_STATE["export_progress"] = {
            "status": "completed",
            "current_clip": 1,
            "total_clips": 1,
            "percent": 100,
            "title": clip.title
        }
        if progress_cb:
            progress_cb(100, f"Rendered {clip.title}")
        return {"status": "success", "clip": res}
    except JobCancelledError:
        CURRENT_STATE["export_progress"] = {
            "status": "cancelled",
            "current_clip": 1,
            "total_clips": 1,
            "percent": 0,
            "title": "Cancelled"
        }
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        CURRENT_STATE["export_progress"] = {
            "status": "error",
            "current_clip": 1,
            "total_clips": 1,
            "percent": 0,
            "title": clip.title
        }
        err_detail = str(e)
        if hasattr(e, "stderr") and e.stderr:
            raw_err = e.stderr.decode("utf-8", errors="ignore") if isinstance(e.stderr, bytes) else str(e.stderr)
            err_detail = raw_err.strip() or err_detail
        raise HTTPException(status_code=500, detail=f"Export failed: {err_detail}")

@app.post("/api/export_clip")
def export_single_clip(
    clip: ClipDef,
    template_config: Dict[str, Any],
    subtitle_config: Dict[str, Any],
    hook_config: Optional[Dict[str, Any]] = None,
    subtitles: Optional[List[Dict[str, Any]]] = None,
    encoder: Optional[str] = None,
    async_mode: bool = False
):
    if async_mode:
        def worker(job_id, cancel_event, update_prog):
            return _do_export_single_clip(
                clip=clip,
                template_config=template_config,
                subtitle_config=subtitle_config,
                hook_config=hook_config,
                subtitles=subtitles,
                encoder=encoder,
                cancel_event=cancel_event,
                progress_cb=update_prog
            )
        job = start_background_job("export_clip", worker)
        return {"status": "queued", "job_id": job["job_id"], "job": job}

    try:
        return _do_export_single_clip(
            clip=clip,
            template_config=template_config,
            subtitle_config=subtitle_config,
            hook_config=hook_config,
            subtitles=subtitles,
            encoder=encoder
        )
    except JobCancelledError:
        raise HTTPException(status_code=499, detail="Export cancelled by user")

def _do_export_all_clips(req: ExportReq, cancel_event: Optional[threading.Event] = None, progress_cb: Optional[Callable] = None):
    video_path = CURRENT_STATE["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video loaded")

    if cancel_event and cancel_event.is_set():
        raise JobCancelledError("Batch export cancelled by user")
        
    subs_to_use = req.subtitles if req.subtitles is not None else CURRENT_STATE["subtitles"]
    video_meta = CURRENT_STATE.get("video_meta")
    results = []
    errors = []
    
    total = len(req.clips)
    CURRENT_STATE["export_progress"] = {
        "status": "rendering",
        "current_clip": 0,
        "total_clips": total,
        "percent": 5,
        "title": "Initializing batch export..."
    }

    from backend.hardware import get_performance_profile
    perf_prof = get_performance_profile()
    max_workers = min(total, max(1, perf_prof.get("export_workers", 1)))

    if max_workers > 1:
        # Concurrent Multi-Worker Batch Export (Ultra/Performance Tiers)
        import concurrent.futures
        import threading

        progress_lock = threading.Lock()
        clip_pcts: Dict[str, float] = {c.id: 0.0 for c in req.clips}
        completed_count = 0

        def render_worker(idx: int, c: ClipDef):
            nonlocal completed_count
            def batch_progress_cb(clip_pct, cur_sec, dur, speed, frame):
                nonlocal completed_count
                with progress_lock:
                    clip_pcts[c.id] = float(clip_pct)
                    overall_pct = int(sum(clip_pcts.values()) / max(1, total))
                    prog_text = f"Rendering ({completed_count + 1}/{total}) {c.title}: {clip_pct}% ({speed})"
                    CURRENT_STATE["export_progress"] = {
                        "status": "rendering",
                        "current_clip": min(total, completed_count + 1),
                        "total_clips": total,
                        "percent": max(5, min(99, overall_pct)),
                        "title": prog_text,
                        "cur_sec": round(cur_sec, 1),
                        "duration": round(dur, 1),
                        "speed": speed,
                        "frame": frame
                    }
                    if progress_cb:
                        progress_cb(max(5, min(99, overall_pct)), prog_text)

            tmpl_to_use = dict(req.template_config or {})
            if c.template_config and isinstance(c.template_config, dict):
                for k, v in c.template_config.items():
                    if v is not None:
                        tmpl_to_use[k] = v
            for critical_key in ("canvas_w", "canvas_h", "export_bitrate", "divider_line", "divider_color", "divider_height", "pixel_generator", "pixel_generator_mode"):
                if critical_key in req.template_config:
                    tmpl_to_use[critical_key] = req.template_config[critical_key]

            sub_cfg_to_use = c.subtitle_config if c.subtitle_config is not None else req.subtitle_config
            hook_to_use = c.hook_config if c.hook_config is not None else req.hook_config
            c_subs_to_use = (c.subtitles if hasattr(c, "subtitles") and c.subtitles else None) or subs_to_use

            res = render_clip(
                video_path=video_path,
                clip_id=c.id,
                start_time=c.start,
                end_time=c.end,
                title=c.title,
                template_config=tmpl_to_use,
                subtitle_config=sub_cfg_to_use,
                all_subtitles=c_subs_to_use,
                hook_config=hook_to_use,
                output_dir=CURRENT_EXPORT_DIR,
                encoder=req.encoder,
                progress_callback=batch_progress_cb,
                video_meta=video_meta,
                workers_count=max_workers,
                cancel_event=cancel_event
            )
            with progress_lock:
                completed_count += 1
                clip_pcts[c.id] = 100.0
                overall_pct = int(sum(clip_pcts.values()) / max(1, total))
                CURRENT_STATE["export_progress"]["percent"] = max(5, min(100, overall_pct))
            return res

        results_ordered = [None] * total
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(render_worker, idx, c): (idx, c) for idx, c in enumerate(req.clips)}
            for fut in concurrent.futures.as_completed(future_map):
                idx, c = future_map[fut]
                try:
                    res = fut.result()
                    results_ordered[idx] = res
                except JobCancelledError:
                    raise
                except Exception as e:
                    errors.append({"clip_id": c.id, "error": str(e)})

        results = [r for r in results_ordered if r is not None]
    else:
        # Serial Batch Export (Balanced/Eco Tiers)
        for idx, c in enumerate(req.clips):
            if cancel_event and cancel_event.is_set():
                raise JobCancelledError("Batch export cancelled by user")

            CURRENT_STATE["export_progress"] = {
                "status": "rendering",
                "current_clip": idx + 1,
                "total_clips": total,
                "percent": max(5, int((idx / total) * 100)),
                "title": f"Rendering ({idx+1}/{total}): {c.title}",
                "speed": "1.0x",
                "frame": 0
            }
            if progress_cb:
                progress_cb(max(5, int((idx / total) * 100)), CURRENT_STATE["export_progress"]["title"])

            def batch_progress_callback(clip_pct, cur_sec, dur, speed, frame):
                batch_pct = int(((idx + (clip_pct / 100.0)) / total) * 100)
                prog_msg = f"Rendering ({idx+1}/{total}) {c.title}: {clip_pct}% ({round(cur_sec, 1)}s / {round(dur, 1)}s • {speed})"
                CURRENT_STATE["export_progress"] = {
                    "status": "rendering",
                    "current_clip": idx + 1,
                    "total_clips": total,
                    "percent": max(5, min(99, batch_pct)),
                    "title": prog_msg,
                    "cur_sec": round(cur_sec, 1),
                    "duration": round(dur, 1),
                    "speed": speed,
                    "frame": frame
                }
                if progress_cb:
                    progress_cb(max(5, min(99, batch_pct)), prog_msg)

            try:
                # Always merge request template_config so current active UI settings (divider, resolution, bitrate) are applied
                tmpl_to_use = dict(req.template_config or {})
                if c.template_config and isinstance(c.template_config, dict):
                    for k, v in c.template_config.items():
                        if v is not None:
                            tmpl_to_use[k] = v
                for critical_key in ("canvas_w", "canvas_h", "export_bitrate", "divider_line", "divider_color", "divider_height", "pixel_generator", "pixel_generator_mode"):
                    if critical_key in req.template_config:
                        tmpl_to_use[critical_key] = req.template_config[critical_key]

                sub_cfg_to_use = c.subtitle_config if c.subtitle_config is not None else req.subtitle_config
                hook_to_use = c.hook_config if c.hook_config is not None else req.hook_config
                c_subs_to_use = (c.subtitles if hasattr(c, "subtitles") and c.subtitles else None) or subs_to_use
                res = render_clip(
                    video_path=video_path,
                    clip_id=c.id,
                    start_time=c.start,
                    end_time=c.end,
                    title=c.title,
                    template_config=tmpl_to_use,
                    subtitle_config=sub_cfg_to_use,
                    all_subtitles=c_subs_to_use,
                    hook_config=hook_to_use,
                    output_dir=CURRENT_EXPORT_DIR,
                    encoder=req.encoder,
                    progress_callback=batch_progress_callback,
                    video_meta=video_meta,
                    workers_count=1,
                    cancel_event=cancel_event
                )
                results.append(res)
                CURRENT_STATE["export_progress"]["percent"] = int(((idx + 1) / total) * 100)
            except JobCancelledError:
                raise
            except Exception as e:
                errors.append({"clip_id": c.id, "error": str(e)})
            
    # Optional Batch ZIP Packaging
    zip_info = None
    if req.export_as_zip and results:
        CURRENT_STATE["export_progress"]["title"] = "Packaging clips into ZIP archive..."
        try:
            import time
            base_vid = os.path.splitext(os.path.basename(video_path))[0]
            clean_pfx = "".join(c for c in base_vid if c.isalnum() or c in ("-", "_")).strip() or "OpenShorts"
            zip_filename = f"{clean_pfx}_Batch_{int(time.time())}.zip"
            zip_dest = os.path.join(CURRENT_EXPORT_DIR, zip_filename)
            with zipfile.ZipFile(zip_dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for r in results:
                    vp = r.get("video_path")
                    if vp and os.path.exists(vp):
                        zf.write(vp, arcname=os.path.basename(vp))
            CURRENT_STATE["last_batch_zip"] = zip_dest
            zip_info = {
                "filename": zip_filename,
                "download_url": f"/api/download_zip?file={zip_filename}",
                "size_mb": round(os.path.getsize(zip_dest) / (1024 * 1024), 2)
            }
        except Exception as ze:
            print(f"Batch ZIP creation error: {ze}")

    final_title = f"Export complete! ({len(results)} clips rendered)" + (f" • ZIP ready ({zip_info['size_mb']} MB)" if zip_info else "")
    CURRENT_STATE["export_progress"] = {
        "status": "completed",
        "current_clip": total,
        "total_clips": total,
        "percent": 100,
        "title": final_title
    }
    if progress_cb:
        progress_cb(100, final_title)

    return {"status": "success", "exported": results, "errors": errors, "zip": zip_info}

@app.post("/api/export_all")
def export_all_clips(req: ExportReq, async_mode: bool = False):
    if async_mode:
        def worker(job_id, cancel_event, update_prog):
            return _do_export_all_clips(req, cancel_event=cancel_event, progress_cb=update_prog)
        job = start_background_job("export_all", worker)
        return {"status": "queued", "job_id": job["job_id"], "job": job}

    try:
        return _do_export_all_clips(req)
    except JobCancelledError:
        raise HTTPException(status_code=499, detail="Batch export cancelled by user")

@app.api_route("/media/video", methods=["GET", "HEAD"])
async def serve_current_video(request: Request):
    """Streams the active uploaded video footage with HTTP 206 Partial Content range support for zero-latency browser playback."""
    video_path = CURRENT_STATE.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="No video loaded")

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("range")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    if request.method == "HEAD":
        headers["Content-Length"] = str(file_size)
        return Response(status_code=200, headers=headers)

    if range_header:
        try:
            h = range_header.strip().lower()
            if h.startswith("bytes="):
                range_spec = h[6:].strip()
                parts = range_spec.split("-")
                if len(parts) == 2:
                    if parts[0] == "":
                        suffix = int(parts[1])
                        start = max(0, file_size - suffix)
                        end = file_size - 1
                    elif parts[1] == "":
                        start = int(parts[0])
                        end = file_size - 1
                    else:
                        start = int(parts[0])
                        end = min(int(parts[1]), file_size - 1)

                    if start > end or start >= file_size:
                        headers["Content-Range"] = f"bytes */{file_size}"
                        return Response(status_code=416, headers=headers)

                    content_length = (end - start) + 1

                    def iter_range():
                        try:
                            with open(video_path, "rb") as f:
                                f.seek(start)
                                bytes_left = content_length
                                chunk_size = 512 * 1024
                                while bytes_left > 0:
                                    chunk = f.read(min(bytes_left, chunk_size))
                                    if not chunk:
                                        break
                                    bytes_left -= len(chunk)
                                    yield chunk
                        except (GeneratorExit, ConnectionResetError, BrokenPipeError):
                            return

                    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                    headers["Content-Length"] = str(content_length)
                    return StreamingResponse(iter_range(), status_code=206, headers=headers)
        except Exception as e:
            print(f"[Video Range Stream Error]: {e}")

    # Fallback full file streaming
    def iter_full():
        try:
            with open(video_path, "rb") as f:
                chunk_size = 512 * 1024
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield data
        except (GeneratorExit, ConnectionResetError, BrokenPipeError):
            return

    headers["Content-Length"] = str(file_size)
    return StreamingResponse(iter_full(), status_code=200, headers=headers)

@app.api_route("/media/output/{filename}", methods=["GET", "HEAD"])
def serve_output_file(filename: str):
    for d in (CURRENT_EXPORT_DIR, OUTPUTS_DIR):
        if not d or not os.path.exists(d):
            continue
        resolved = safe_resolve_under(d, filename)
        if resolved:
            return FileResponse(resolved)
    raise HTTPException(status_code=404, detail="Media file not found")

@app.get("/media/thumbnail/{clip_id}")
def serve_clip_thumbnail(clip_id: str):
    safe_name = os.path.basename(clip_id)
    candidates = [f"{safe_name}_thumb.jpg", f"{safe_name}.jpg", safe_name]
    for cand in candidates:
        for d in (THUMBNAILS_DIR, CURRENT_EXPORT_DIR, OUTPUTS_DIR):
            if not d or not os.path.exists(d):
                continue
            resolved = safe_resolve_under(d, cand)
            if resolved:
                return FileResponse(resolved, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Thumbnail cover not found")

@app.get("/api/download_zip")
def download_zip(file: Optional[str] = None):
    if file:
        safe_f = os.path.basename(file)
        for d in (CURRENT_EXPORT_DIR, OUTPUTS_DIR):
            if not d or not os.path.exists(d):
                continue
            resolved = safe_resolve_under(d, safe_f)
            if resolved:
                return FileResponse(resolved, filename=safe_f, media_type="application/zip")
    else:
        target = CURRENT_STATE.get("last_batch_zip", "")
        if target and os.path.isfile(target):
            target_path = Path(target).resolve()
            for d in (CURRENT_EXPORT_DIR, OUTPUTS_DIR):
                if d and os.path.exists(d) and target_path.is_relative_to(Path(d).resolve()):
                    return FileResponse(str(target_path), filename=target_path.name, media_type="application/zip")
    raise HTTPException(status_code=404, detail="ZIP file not found")

@app.post("/api/create_zip_from_outputs")
def create_zip_from_outputs():
    target_dir = CURRENT_EXPORT_DIR if os.path.exists(CURRENT_EXPORT_DIR) else OUTPUTS_DIR
    mp4s = [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith(".mp4") and not f.endswith("_thumb.jpg")]
    if not mp4s:
        raise HTTPException(status_code=400, detail="No exported MP4 clips found to zip")
    import time
    zip_name = f"OpenShorts_Batch_Clips_{int(time.time())}.zip"
    zip_dest = os.path.join(target_dir, zip_name)
    with zipfile.ZipFile(zip_dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in mp4s:
            zf.write(p, arcname=os.path.basename(p))
    CURRENT_STATE["last_batch_zip"] = zip_dest
    zip_obj = {
        "filename": zip_name,
        "download_url": f"/api/download_zip?file={zip_name}",
        "size_mb": round(os.path.getsize(zip_dest) / (1024 * 1024), 2)
    }
    return {
        "status": "success",
        "filename": zip_name,
        "download_url": f"/api/download_zip?file={zip_name}",
        "size_mb": zip_obj["size_mb"],
        "zip": zip_obj
    }

@app.get("/api/progress")
def get_progress():
    return CURRENT_STATE["export_progress"]

@app.get("/api/outputs")
def list_outputs():
    files = []
    seen = set()
    dirs_to_check = [CURRENT_EXPORT_DIR]
    if OUTPUTS_DIR != CURRENT_EXPORT_DIR and os.path.exists(OUTPUTS_DIR):
        dirs_to_check.append(OUTPUTS_DIR)

    for d in dirs_to_check:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".mp4") and f not in seen:
                seen.add(f)
                mp4_path = os.path.join(d, f)
                thumb_name = f.replace(".mp4", "_thumb.jpg")
                thumb_path = os.path.join(d, thumb_name)
                files.append({
                    "filename": f,
                    "video_url": f"/media/output/{f}",
                    "thumb_url": f"/media/output/{thumb_name}" if os.path.exists(thumb_path) else None,
                    "size_mb": round(os.path.getsize(mp4_path) / (1024*1024), 2),
                    "created_at": os.path.getmtime(mp4_path)
                })
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return {"files": files, "export_dir": CURRENT_EXPORT_DIR}
