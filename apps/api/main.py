from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, BackgroundTasks, Response, Request
from pydantic import BaseModel
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import or_, and_
import os
import uuid
import shutil
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone

# Local modules (keep all imports at top for lint/clarity)
from security_core.privacy_guard import sanitize_for_logging, assert_no_content
from database import get_db, engine, SessionLocal
from models import (
    Project,
    ProjectEvent,
    Document,
    ProjectNote,
    JournalistNote,
    JournalistNoteImage,
    ProjectSource,
    ScoutFeed,
    ScoutItem,
    KnoxReport,
    AiJob,
    AiJobStatus,
    Base,
    Classification,
    SanitizeLevel,
    NoteCategory,
    SourceType,
    ProjectStatus,
)
from schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectEventCreate,
    ProjectEventResponse,
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NoteListResponse,
    JournalistNoteCreate,
    JournalistNoteUpdate,
    JournalistNoteResponse,
    JournalistNoteListResponse,
    JournalistNoteImageResponse,
    ProjectSourceCreate,
    ProjectSourceResponse,
    ProjectSourceUpdate,
    ProjectStatusUpdate,
    ScoutFeedCreate,
    ScoutFeedUpdate,
    ScoutFeedResponse,
    ScoutItemResponse,
    AiJobResponse,
    FeedPreviewResponse,
    FeedItemPreview,
    CreateProjectFromFeedRequest,
    CreateProjectFromFeedResponse,
    CreateProjectFromScoutItemRequest,
    CreateProjectFromScoutItemResponse,
    KnoxCompileRequest,
    KnoxReportResponse,
    KnoxErrorResponse,
)
from text_processing import (
    extract_text_from_pdf,
    extract_text_from_txt,
    normalize_text,
    mask_text,
    mask_datetime,
    validate_file_type,
    pii_gate_check,
    transcribe_audio,
    normalize_transcript_text,
    process_transcript,
    refine_editorial_text,
    sanitize_journalist_note,
)
from fortknox import (
    build_knox_input_pack,
    input_gate,
    re_id_guard,
    render_markdown,
    get_policy,
    canonical_json,
    compute_sha256,
    break_quote_ngrams,
)
from fortknox_remote import compile_remote, FortKnoxRemoteError
from fortknox_langchain import compile_with_langchain, FortKnoxLangChainConfigError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _safe_event_metadata(meta: dict, context: str = "audit") -> dict:
    """
    Helper function to sanitize event metadata using Privacy Guard.
    
    Args:
        meta: Raw metadata dictionary
        context: Context for sanitization ("audit" or "log")
        
    Returns:
        Sanitized metadata dictionary (forbidden keys removed/truncated)
        
    Raises:
        AssertionError: In DEV mode if forbidden keys found
    """
    sanitized = sanitize_for_logging(meta, context=context)
    assert_no_content(sanitized, context=context)
    return sanitized

def _job_to_response(job: AiJob) -> AiJobResponse:
    return AiJobResponse(
        id=job.id,
        kind=job.kind,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        progress=job.progress,
        project_id=job.project_id,
        actor=job.actor,
        payload=job.payload,
        result=job.result,
        error_code=job.error_code,
        error_detail=job.error_detail,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _update_job(job_id: int, **fields):
    """Best-effort uppdatering av jobbstatus (metadata-only)."""
    db = SessionLocal()
    try:
        job = db.query(AiJob).filter(AiJob.id == job_id).first()
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        db.commit()
    finally:
        db.close()


def _safe_job_result(data: Optional[dict]) -> Optional[dict]:
    """Plocka endast metadata/ids (aldrig textfält)."""
    if not isinstance(data, dict):
        return None
    # Conservative allow-list
    allowed = {
        "id",
        "project_id",
        "policy_id",
        "policy_version",
        "template_id",
        "engine_id",
        "input_fingerprint",
        "ruleset_hash",
        "created_at",
        "latency_ms",
        "filename",
        "file_type",
        "sanitize_level",
    }
    return {k: v for k, v in data.items() if k in allowed}


def _run_job_http_post(
    job_id: int,
    url: str,
    *,
    json_body: Optional[dict] = None,
    files: Optional[dict] = None,
    auth_user: str = "",
    auth_pass: str = ""
):
    """
    Kör ett jobb genom att anropa vår egen API-endpoint (återanvänd pipeline utan duplicering).
    Loggar aldrig innehåll; endast status/ids.
    """
    import time
    import requests

    _update_job(job_id, status=AiJobStatus.RUNNING, progress=10)
    started = time.time()
    try:
        r = requests.post(
            url,
            json=json_body,
            files=files,
            auth=(auth_user, auth_pass) if auth_user and auth_pass else None,
            timeout=180
        )
        latency_ms = int((time.time() - started) * 1000)
        if r.status_code >= 200 and r.status_code < 300:
            data = None
            if (r.headers.get("content-type", "") or "").startswith("application/json"):
                try:
                    data = r.json()
                except Exception:
                    data = None
            _update_job(
                job_id,
                status=AiJobStatus.SUCCEEDED,
                progress=100,
                result={
                    "http_status": r.status_code,
                    "latency_ms": latency_ms,
                    "data": _safe_job_result(data),
                },
            )
            return

        # Fail: försök plocka ut felkod/metadata
        payload = None
        try:
            payload = r.json()
        except Exception:
            payload = None

        error_code = None
        error_detail = None
        if isinstance(payload, dict):
            # KnoxErrorResponse ligger ofta i "detail" (FastAPI HTTPException)
            detail = payload.get("detail")
            if isinstance(detail, dict):
                error_code = detail.get("error_code")
                error_detail = detail.get("detail") or payload.get("detail")
            else:
                error_detail = payload.get("detail") if isinstance(payload.get("detail"), str) else None
        _update_job(
            job_id,
            status=AiJobStatus.FAILED,
            progress=100,
            error_code=error_code or f"HTTP_{r.status_code}",
            error_detail=(error_detail or "Job failed"),
        )
    except Exception as e:
        _update_job(
            job_id,
            status=AiJobStatus.FAILED,
            progress=100,
            error_code="JOB_EXCEPTION",
            error_detail=type(e).__name__,
        )

def run_sanitize_pipeline(raw_text: str) -> Dict:
    """
    Run full sanitization pipeline on raw text (same as document ingest).
    
    Returns:
        Dict with keys: ok (bool), masked_text (str), sanitize_level (SanitizeLevel),
        pii_gate_reasons (dict or None), usage_restrictions (dict),
        datetime_masked (bool), datetime_mask_count (int)
        
    Raises:
        Exception if pipeline fails (fail-closed)
    """
    # Normalize
    normalized_text = normalize_text(raw_text)
    
    # Progressive sanitization
    pii_gate_reasons = {}
    sanitize_level = SanitizeLevel.NORMAL
    usage_restrictions = {"ai_allowed": True, "export_allowed": True}
    masked_text = None
    datetime_masked = False
    datetime_mask_count = 0
    
    # Try normal masking
    masked_text = mask_text(normalized_text, level="normal")
    is_safe, reasons = pii_gate_check(masked_text)
    if is_safe:
        sanitize_level = SanitizeLevel.NORMAL
        pii_gate_reasons = None
    else:
        pii_gate_reasons["normal"] = reasons
        
        # Try strict masking
        masked_text = mask_text(normalized_text, level="strict")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.STRICT
            usage_restrictions = {"ai_allowed": True, "export_allowed": True}
        else:
            pii_gate_reasons["strict"] = reasons
            
            # Use paranoid masking
            masked_text = mask_text(normalized_text, level="paranoid")
            is_safe, reasons = pii_gate_check(masked_text)
            
            if not is_safe:
                # Fail-closed: this should never happen, but if it does, raise
                raise Exception(f"Paranoid masking failed PII gate: {reasons}")
            
            sanitize_level = SanitizeLevel.PARANOID
            usage_restrictions = {"ai_allowed": False, "export_allowed": False}
    
    # DATUM/TID-MASKNING: alltid körs för strict/paranoid (fail-closed mot extern export)
    if sanitize_level in (SanitizeLevel.STRICT, SanitizeLevel.PARANOID):
        level_str = "paranoid" if sanitize_level == SanitizeLevel.PARANOID else "strict"
        masked_text, datetime_stats = mask_datetime(masked_text, level=level_str)
        datetime_masked = datetime_stats["datetime_masked"]
        datetime_mask_count = datetime_stats["datetime_mask_count"]
    
    return {
        "ok": True,
        "masked_text": masked_text,
        "sanitize_level": sanitize_level,
        "pii_gate_reasons": pii_gate_reasons,
        "usage_restrictions": usage_restrictions,
        "datetime_masked": datetime_masked,
        "datetime_mask_count": datetime_mask_count
    }

# Create tables
Base.metadata.create_all(bind=engine)

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Arbetsytan API")

try:
    # Optional, but installed in demo image: Prometheus metrics
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

    HTTP_REQUESTS_TOTAL = Counter(
        "arbetsytan_http_requests_total",
        "Total number of HTTP requests",
        ["method", "route", "status"],
    )
    HTTP_REQUEST_LATENCY_SECONDS = Histogram(
        "arbetsytan_http_request_latency_seconds",
        "HTTP request latency in seconds",
        ["method", "route", "status"],
    )
except Exception:
    # Fail-open for metrics: app must still start (demo-safe)
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_LATENCY_SECONDS = None
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


@app.middleware("http")
async def request_timing_middleware(request, call_next):
    """
    Lightweight observability:
    - Adds X-Request-Id header
    - Logs method/path/status/latency (no content, no query params)
    """
    import time
    rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    start = time.time()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        latency_s = (time.time() - start)
        latency_ms = int(latency_s * 1000)
        status_code = getattr(response, "status_code", "ERR")
        logger.info(f"REQ {request.method} {request.url.path} {status_code} {latency_ms}ms rid={rid[:8]}")

        # Metrics (metadata-only): label on route template when available to avoid high-cardinality
        if HTTP_REQUESTS_TOTAL is not None and HTTP_REQUEST_LATENCY_SECONDS is not None:
            if request.url.path != "/api/metrics":
                route_obj = request.scope.get("route")
                route_label = getattr(route_obj, "path", None) or request.url.path
                status_label = str(status_code)
                HTTP_REQUESTS_TOTAL.labels(request.method, route_label, status_label).inc()
                HTTP_REQUEST_LATENCY_SECONDS.labels(request.method, route_label, status_label).observe(latency_s)
        if response is not None:
            response.headers["X-Request-Id"] = rid


# Preload STT engine at startup (to avoid blocking first transcription)
@app.on_event("startup")
async def preload_stt_engine():
    """Preload STT engine at startup to avoid blocking first transcription request."""
    # Demo-safe default: gör inte cold-start långsam eller nätverksberoende.
    # Slå på explicit med PRELOAD_STT=1 om du vill.
    if os.getenv("PRELOAD_STT", "0").strip() != "1":
        logger.info("[STARTUP] STT preload disabled (set PRELOAD_STT=1 to enable).")
        return
    try:
        from text_processing import _get_stt_engine
        logger.info("[STARTUP] Preloading STT engine...")
        engine, model, engine_name, model_name = _get_stt_engine()
        logger.info(f"[STARTUP] STT engine preloaded successfully: {engine_name}, model: {model_name}")
    except Exception as e:
        logger.warning(f"[STARTUP] Failed to preload STT engine: {str(e)} (will load on first use)")

# CORS middleware
# - Dev: localhost
# - Prod demo (Tailscale Funnel): set CORS_ALLOW_ORIGINS="https://{DOMAIN_ROOT}"
cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:5173")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic Auth
# NOTE: auto_error=False is required so AUTH_MODE=public can work without triggering browser login prompts.
security = HTTPBasic(auto_error=False)

# Environment variables
AUTH_MODE = os.getenv("AUTH_MODE", "basic")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
# Backwards compatible envs (legacy)
BASIC_AUTH_USER = os.getenv("BASIC_AUTH_USER", "admin")
BASIC_AUTH_PASS = os.getenv("BASIC_AUTH_PASS", "password")

# Auth-ram: stöd för två roller i Basic Auth (admin/editor)
# - Admin creds defaultar till legacy BASIC_AUTH_*
# - Editor creds är optional. Om ej satta finns bara admin.
BASIC_AUTH_ADMIN_USER = os.getenv("BASIC_AUTH_ADMIN_USER", BASIC_AUTH_USER)
BASIC_AUTH_ADMIN_PASS = os.getenv("BASIC_AUTH_ADMIN_PASS", BASIC_AUTH_PASS)
BASIC_AUTH_EDITOR_USER = os.getenv("BASIC_AUTH_EDITOR_USER", "").strip()
BASIC_AUTH_EDITOR_PASS = os.getenv("BASIC_AUTH_EDITOR_PASS", "").strip()

# Async jobs (STT/LLM) - off by default (demo-safe)
ASYNC_JOBS_ENABLED = os.getenv("ASYNC_JOBS", "0").strip() == "1"

# Rate limiting (demo-safe defaults)
RATE_LIMITS_ENABLED = os.getenv("RATE_LIMITS", "1").strip() == "1"
_rate_limit_state: Dict[str, List[float]] = {}


def _rate_limit_check(key: str, limit: int, window_seconds: int) -> None:
    """
    Minimal in-memory rate limiter (per-process).
    - key: t.ex. "user:bucket"
    - limit: max antal events per window
    - window_seconds: fönsterstorlek i sekunder
    """
    import time

    now = time.time()
    window_start = now - window_seconds
    hits = _rate_limit_state.get(key, [])
    hits = [t for t in hits if t >= window_start]

    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    hits.append(now)
    _rate_limit_state[key] = hits


def rate_limit(bucket: str, default_per_minute: int):
    """FastAPI dependency factory for rate limiting per authenticated user."""

    def _dep(username: str = Depends(verify_basic_auth)):
        if not RATE_LIMITS_ENABLED:
            return True
        # Allow override per bucket via env, e.g. RATE_LIMIT_FORTKNOX_COMPILE_PER_MIN=3
        env_key = f"RATE_LIMIT_{bucket.upper()}_PER_MIN"
        limit = int(os.getenv(env_key, str(default_per_minute)).strip())
        _rate_limit_check(key=f"{username}:{bucket}", limit=limit, window_seconds=60)
        return True

    return _dep


def _role_for_username(username: str) -> str:
    # In basic auth mode, map usernames to roles.
    if AUTH_MODE == "basic":
        if username == BASIC_AUTH_ADMIN_USER:
            return "admin"
        if BASIC_AUTH_EDITOR_USER and username == BASIC_AUTH_EDITOR_USER:
            return "editor"
        # Default: om det bara finns en användare i demo så är den admin.
        return "admin"
    # In public/non-basic mode, no user should be treated as admin by default.
    return "public"


def verify_basic_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    """Verify Basic Auth credentials"""
    if AUTH_MODE != "basic":
        # Public mode: do not challenge browser with Basic Auth.
        # NOTE: admin-only endpoints must remain protected via require_admin().
        return "public"

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    is_admin = (
        credentials.username == BASIC_AUTH_ADMIN_USER
        and credentials.password == BASIC_AUTH_ADMIN_PASS
    )
    is_editor = (
        BASIC_AUTH_EDITOR_USER
        and BASIC_AUTH_EDITOR_PASS
        and credentials.username == BASIC_AUTH_EDITOR_USER
        and credentials.password == BASIC_AUTH_EDITOR_PASS
    )

    if not (is_admin or is_editor):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def require_admin(request: Request, username: str = Depends(verify_basic_auth)):
    """
    Policy gate: endast admin får utföra destruktiva åtgärder.

    - AUTH_MODE=basic: Basic Auth admin/editor som tidigare.
    - AUTH_MODE!=basic (public demo): kräver ADMIN_TOKEN via header `X-Admin-Token`.
      Om ADMIN_TOKEN inte är satt, blockas admin-endpoints helt (fail-closed).
    """
    if AUTH_MODE == "basic":
        if _role_for_username(username) != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges required")
        return True

    required = os.getenv("ADMIN_TOKEN", "").strip()
    provided = (request.headers.get("X-Admin-Token", "") or "").strip()
    if not required or provided != required:
        raise HTTPException(status_code=403, detail="Admin token required")
    return True


@app.get("/api/metrics", response_class=PlainTextResponse)
async def metrics(_: bool = Depends(require_admin)):
    """
    Prometheus metrics endpoint (admin-only).

    Innehåller endast räknare/tider (ingen rådata).
    """
    if generate_latest is None:
        raise HTTPException(status_code=503, detail="Metrics not available")
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.get("/api/jobs/{job_id}", response_model=AiJobResponse)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Hämta status för ett bakgrundsjobb (metadata-only)."""
    job = db.query(AiJob).filter(AiJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


async def health_check():
    """Health check handler (no auth required)"""
    return {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "auth_mode": AUTH_MODE,
        "async_jobs": ASYNC_JOBS_ENABLED
    }


@app.get("/health")
async def health():
    """Health check endpoint (no auth required)"""
    return await health_check()


@app.get("/api/health")
async def api_health():
    """Health check endpoint (no auth required) - API prefix version"""
    return await health_check()


@app.get("/api/hello")
async def hello(username: str = Depends(verify_basic_auth)):
    """Protected hello endpoint"""
    return {
        "message": f"Hello, {username}!",
        "demo_mode": DEMO_MODE
    }


# Projects endpoints
@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """List all projects"""
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    return projects


@app.post("/api/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Create a new project"""
    db_project = Project(
        name=project.name,
        description=project.description,
        classification=project.classification,
        due_date=project.due_date,
        tags=project.tags
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    # Create initial event
    event = ProjectEvent(
        project_id=db_project.id,
        event_type="project_created",
        actor=username,
        event_metadata=_safe_event_metadata({"name": project.name}, context="audit")
    )
    db.add(event)
    db.commit()
    
    return db_project


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get a specific project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Update a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Track changes for event metadata
    changes = {}
    
    if project_update.name is not None:
        if project.name != project_update.name:
            changes["name"] = {"old": project.name, "new": project_update.name}
        project.name = project_update.name
    
    if project_update.description is not None:
        if project.description != project_update.description:
            changes["description"] = {"old": project.description, "new": project_update.description}
        project.description = project_update.description
    
    if project_update.classification is not None:
        if project.classification != project_update.classification:
            changes["classification"] = {"old": project.classification.value, "new": project_update.classification.value}
        project.classification = project_update.classification
    
    if project_update.due_date is not None:
        if project.due_date != project_update.due_date:
            changes["due_date"] = {
                "old": str(project.due_date) if project.due_date else None,
                "new": str(project_update.due_date) if project_update.due_date else None,
            }
        project.due_date = project_update.due_date
    
    if project_update.tags is not None:
        if project.tags != project_update.tags:
            changes["tags"] = {"old": project.tags, "new": project_update.tags}
        project.tags = project_update.tags
    
    # Update updated_at is automatic via onupdate
    
    db.commit()
    db.refresh(project)
    
    # Create event if any changes were made
    if changes:
        event = ProjectEvent(
            project_id=project.id,
            event_type="project_updated",
            actor=username,
            event_metadata=_safe_event_metadata({"changes": changes}, context="audit")
        )
        db.add(event)
        db.commit()
    
    return project


@app.patch("/api/projects/{project_id}/status", response_model=ProjectResponse)
async def update_project_status(
    project_id: int,
    status_update: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Update project status and log event."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    old_status = project.status.value
    new_status = status_update.status.value
    
    # Update status
    project.status = status_update.status
    db.commit()
    db.refresh(project)
    
    # Log event (metadata only, via Privacy Guard)
    event_metadata = _safe_event_metadata({
        "from": old_status,
        "to": new_status
    }, context="audit")
    
    event = ProjectEvent(
        project_id=project_id,
        event_type="project_status_changed",
        actor=username,
        event_metadata=event_metadata
    )
    db.add(event)
    db.commit()
    
    logger.info(f"Project {project_id} status changed: {old_status} -> {new_status}")
    
    return project


@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    username: str = Depends(verify_basic_auth)
):
    """
    Delete a project and all its documents and events (permanent).
    
    Security by Design:
    - Counts files before delete
    - Deletes all files from disk
    - Verifies no orphans remain
    - Logs only metadata (no filenames/paths)
    - Fail-closed: if verification fails, log error and block delete
    """
    import os
    from pathlib import Path
    from security_core.privacy_guard import sanitize_for_logging
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # === PHASE 1: Count all files before delete ===
    files_to_delete = []
    
    # 1. Document files
    documents = db.query(Document).filter(Document.project_id == project_id).all()
    for doc in documents:
        if doc.file_path:
            file_path = UPLOAD_DIR / doc.file_path
            if file_path.exists():
                files_to_delete.append(file_path)
    
    # 2. Recording files (audio files for transcripts)
    # Note: Recordings are stored as documents with file_path, already counted above
    
    # 3. Journalist note images
    journalist_notes = db.query(JournalistNote).filter(JournalistNote.project_id == project_id).all()
    for note in journalist_notes:
        for image in note.images:
            if image.file_path:
                image_path = Path(image.file_path)
                if image_path.exists():
                    files_to_delete.append(image_path)
    
    file_count_before = len(files_to_delete)
    
    logger.info(f"[SECURE_DELETE] Project {project_id}: Found {file_count_before} files to delete")
    
    # === PHASE 2: Delete files from disk ===
    deleted_files = 0
    failed_deletes = []
    
    for file_path in files_to_delete:
        try:
            os.remove(file_path)
            deleted_files += 1
        except Exception as e:
            logger.warning(f"[SECURE_DELETE] Failed to delete file: {type(e).__name__}")
            failed_deletes.append(str(file_path))
    
    # === PHASE 3: Verify no orphans remain ===
    orphans = []
    for file_path in files_to_delete:
        if file_path.exists():
            orphans.append(str(file_path))
    
    # Fail-closed: if orphans detected, log error and block delete
    if orphans:
        logger.error(f"[SECURE_DELETE] Project {project_id}: ORPHAN DETECTION FAILED - {len(orphans)} files remain on disk")
        raise HTTPException(
            status_code=500,
            detail=f"Secure delete failed: {len(orphans)} orphan files detected. Delete blocked for security."
        )
    
    # === PHASE 4: Delete DB records (CASCADE) ===
    # Delete events first (explicit cascade)
    db.query(ProjectEvent).filter(ProjectEvent.project_id == project_id).delete()
    # Delete documents (cascade should handle, but explicit for safety)
    db.query(Document).filter(Document.project_id == project_id).delete()
    # Delete project sources (avoid ORM trying to NULL fk on parent delete)
    db.query(ProjectSource).filter(ProjectSource.project_id == project_id).delete()
    # Delete project notes (cascade will delete journalist notes and images)
    db.query(ProjectNote).filter(ProjectNote.project_id == project_id).delete()
    db.query(JournalistNote).filter(JournalistNote.project_id == project_id).delete()
    # Delete Knox reports (JSON manifest rows)
    db.query(KnoxReport).filter(KnoxReport.project_id == project_id).delete()
    # Delete project
    db.delete(project)
    db.commit()
    
    # === PHASE 5: Log only metadata (privacy-safe) ===
    safe_metadata = sanitize_for_logging({
        "project_id": project_id,
        "files_counted": file_count_before,
        "files_deleted": deleted_files,
        "files_failed": len(failed_deletes),
        "orphans_detected": len(orphans),
        "actor": username
    }, context="audit")
    
    logger.info(f"[SECURE_DELETE] Project {project_id} deleted successfully", extra=safe_metadata)
    
    return None


@app.get("/api/projects/{project_id}/events", response_model=List[ProjectEventResponse])
async def get_project_events(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get events for a specific project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    events = db.query(ProjectEvent).filter(
        ProjectEvent.project_id == project_id
    ).order_by(ProjectEvent.timestamp.desc()).all()
    return events


@app.post("/api/projects/{project_id}/events", response_model=ProjectEventResponse, status_code=201)
async def create_project_event(
    project_id: int,
    event: ProjectEventCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Create an event for a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_event = ProjectEvent(
        project_id=project_id,
        event_type=event.event_type,
        actor=event.actor or username,
        event_metadata=_safe_event_metadata(event.metadata or {}, context="audit")
    )
    db.add(db_event)
    
    # Update project updated_at
    from sqlalchemy.sql import func
    project.updated_at = func.now()
    
    db.commit()
    db.refresh(db_event)
    return db_event


# Documents endpoints
@app.post("/api/projects/{project_id}/documents", response_model=DocumentListResponse, status_code=201)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth),
    _: bool = Depends(rate_limit("upload", 20)),
):
    """
    Upload a document to a project.
    Returns metadata only (no masked_text).
    """
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate file size (25MB max)
    file_content = await file.read()
    if len(file_content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 25MB")
    
    # Save file temporarily for validation and processing
    temp_path = UPLOAD_DIR / f"temp_{uuid.uuid4()}"
    try:
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        
        # Validate file type (extension + magic bytes)
        file_type, is_valid = validate_file_type(str(temp_path), file.filename)
        if not is_valid:
            os.remove(temp_path)
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF and TXT files are allowed. PDF must start with %PDF-, TXT must be valid text."
            )
        
        # Extract text
        try:
            if file_type == 'pdf':
                raw_text = extract_text_from_pdf(str(temp_path))
            else:  # txt
                raw_text = extract_text_from_txt(str(temp_path))
        except Exception as e:
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail=f"Failed to extract text: {str(e)}")
        
        # Normalize text
        normalized_text = normalize_text(raw_text)
        
        # Progressive sanitization pipeline
        pii_gate_reasons = {}
        sanitize_level = SanitizeLevel.NORMAL
        usage_restrictions = {"ai_allowed": True, "export_allowed": True}
        masked_text = None
        
        # Try normal masking
        masked_text = mask_text(normalized_text, level="normal")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.NORMAL
            pii_gate_reasons = None
        else:
            pii_gate_reasons["normal"] = reasons
            
            # Try strict masking
            masked_text = mask_text(normalized_text, level="strict")
            is_safe, reasons = pii_gate_check(masked_text)
            if is_safe:
                sanitize_level = SanitizeLevel.STRICT
                usage_restrictions = {"ai_allowed": True, "export_allowed": True}
            else:
                pii_gate_reasons["strict"] = reasons
                
                # Use paranoid masking (must always pass gate)
                masked_text = mask_text(normalized_text, level="paranoid")
                is_safe, reasons = pii_gate_check(masked_text)
                
                if not is_safe:
                    # This should never happen - paranoid must guarantee gate pass
                    os.remove(temp_path)
                    raise HTTPException(
                        status_code=500,
                        detail="Internal error: Paranoid masking failed PII gate check. This is a bug."
                    )
                
                sanitize_level = SanitizeLevel.PARANOID
                usage_restrictions = {"ai_allowed": False, "export_allowed": False}
        
        # Move file to permanent location
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        permanent_path = UPLOAD_DIR / f"{file_id}{file_ext}"
        shutil.move(str(temp_path), str(permanent_path))
        
        # Create document record
        db_document = Document(
            project_id=project_id,
            filename=file.filename,
            file_type=file_type,
            classification=project.classification,  # Inherit from project
            masked_text=masked_text,
            file_path=str(permanent_path),  # Never exposed via API
            sanitize_level=sanitize_level,
            usage_restrictions=usage_restrictions,
            pii_gate_reasons=pii_gate_reasons if pii_gate_reasons else None
        )
        db.add(db_document)
        
        # Update project updated_at
        from sqlalchemy.sql import func
        project.updated_at = func.now()
        
        # Create event
        event = ProjectEvent(
            project_id=project_id,
            event_type="document_uploaded",
            actor=username,
            event_metadata=_safe_event_metadata({"file_type": file_type}, context="audit")
        )
        db.add(event)
        
        db.commit()
        db.refresh(db_document)
        
        # Return metadata only (no masked_text)
        return DocumentListResponse(
            id=db_document.id,
            project_id=db_document.project_id,
            filename=db_document.filename,
            file_type=db_document.file_type,
            classification=db_document.classification.value,
            sanitize_level=db_document.sanitize_level.value,
            usage_restrictions=db_document.usage_restrictions,
            pii_gate_reasons=db_document.pii_gate_reasons,
            created_at=db_document.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on error
        if temp_path.exists():
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/projects/{project_id}/documents", response_model=List[DocumentListResponse])
async def list_documents(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    List all documents for a project.
    Returns metadata only (no masked_text, no file_path).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    documents = db.query(Document).filter(
        Document.project_id == project_id
    ).order_by(Document.created_at.desc()).all()
    
    return [
        DocumentListResponse(
            id=doc.id,
            project_id=doc.project_id,
            filename=doc.filename,
            file_type=doc.file_type,
            classification=doc.classification.value,
            sanitize_level=doc.sanitize_level.value,
            usage_restrictions=doc.usage_restrictions,
            pii_gate_reasons=doc.pii_gate_reasons,
            created_at=doc.created_at
        )
        for doc in documents
    ]


@app.get("/api/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Get a specific document.
    Returns masked_text + metadata only (no file_path).
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse(
        id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        file_type=document.file_type,
        classification=document.classification.value,
        masked_text=document.masked_text,
        sanitize_level=document.sanitize_level.value,
        usage_restrictions=document.usage_restrictions,
        pii_gate_reasons=document.pii_gate_reasons,
        created_at=document.created_at
    )


@app.put("/api/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Update a document's masked_text.
    The text will go through the same normalize/mask/sanitization pipeline.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Normalize text
    normalized_text = normalize_text(document_update.masked_text)
    
    # Progressive sanitization pipeline (same as documents)
    pii_gate_reasons = {}
    sanitize_level = SanitizeLevel.NORMAL
    
    # Try normal masking
    masked_text = mask_text(normalized_text, level="normal")
    is_safe, reasons = pii_gate_check(masked_text)
    if is_safe:
        sanitize_level = SanitizeLevel.NORMAL
        pii_gate_reasons = None
    else:
        pii_gate_reasons["normal"] = reasons
        
        # Try strict masking
        masked_text = mask_text(normalized_text, level="strict")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.STRICT
            usage_restrictions = {"ai_allowed": True, "export_allowed": True}
        else:
            pii_gate_reasons["strict"] = reasons
            
            # Use paranoid masking
            masked_text = mask_text(normalized_text, level="paranoid")
            sanitize_level = SanitizeLevel.PARANOID

    # DATUM/TID-maskning: alltid för strict/paranoid
    if sanitize_level in (SanitizeLevel.STRICT, SanitizeLevel.PARANOID):
        level_str = "paranoid" if sanitize_level == SanitizeLevel.PARANOID else "strict"
        masked_text, _datetime_stats = mask_datetime(masked_text, level=level_str)

    # DATUM/TID-maskning: körs alltid för strict/paranoid
    if sanitize_level in (SanitizeLevel.STRICT, SanitizeLevel.PARANOID):
        level_str = "paranoid" if sanitize_level == SanitizeLevel.PARANOID else "strict"
        masked_text, _datetime_stats = mask_datetime(masked_text, level=level_str)
    
    # Update document
    document.masked_text = masked_text
    document.sanitize_level = sanitize_level
    document.pii_gate_reasons = pii_gate_reasons if pii_gate_reasons else None
    document.usage_restrictions = usage_restrictions
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=document.project_id,
        event_type="document_updated",
        actor=username,
        event_metadata=_safe_event_metadata({
            "document_id": document_id,
            "file_type": document.file_type
        }, context="audit")
    )
    db.add(event)
    
    # Update project updated_at
    from sqlalchemy.sql import func
    project = db.query(Project).filter(Project.id == document.project_id).first()
    if project:
        project.updated_at = func.now()
    
    db.commit()
    db.refresh(document)
    
    return DocumentResponse(
        id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        file_type=document.file_type,
        classification=document.classification.value,
        masked_text=document.masked_text,
        sanitize_level=document.sanitize_level.value,
        usage_restrictions=document.usage_restrictions,
        pii_gate_reasons=document.pii_gate_reasons,
        created_at=document.created_at
    )

@app.delete("/api/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    username: str = Depends(verify_basic_auth)
):
    """
    Delete a document and its associated files.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    project_id = document.project_id
    file_type = document.file_type

    # Delete associated files if they exist
    import os
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            # No paths/content in logs (showreel-safe)
            logger.warning(f"Failed to delete document file: doc_id={document_id} err={type(e).__name__}")
    
    # Delete audio file if it exists (for recordings)
    if hasattr(document, 'audio_path') and document.audio_path and os.path.exists(document.audio_path):
        try:
            os.remove(document.audio_path)
        except Exception as e:
            logger.warning(f"Failed to delete audio file: doc_id={document_id} err={type(e).__name__}")
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=project_id,
        event_type="document_deleted",
        actor=username,
        event_metadata=_safe_event_metadata({
            "document_id": document_id,
            "file_type": file_type
        }, context="audit")
    )
    db.add(event)

    # Delete from database
    db.delete(document)

    # Update project updated_at
    from sqlalchemy.sql import func
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.updated_at = func.now()

    db.commit()

    return Response(status_code=204)


@app.put("/api/projects/{project_id}/documents/{document_id}/exclude-from-fortknox", response_model=DocumentResponse)
async def exclude_document_from_fortknox(
    project_id: int,
    document_id: int,
    exclude: bool = Query(default=True),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Exkludera eller inkludera ett dokument från Fort Knox-sammanställningar.
    
    Metadata-only operation:
    - Uppdaterar usage_restrictions.fortknox_excluded
    - Loggar aldrig originaltext
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.project_id == project_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update usage_restrictions
    if not document.usage_restrictions:
        document.usage_restrictions = {}
    
    document.usage_restrictions['fortknox_excluded'] = exclude
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=project_id,
        event_type="document_fortknox_exclusion_changed",
        actor=username,
        event_metadata=_safe_event_metadata({
            "document_id": document_id,
            "excluded": exclude,
            "file_type": document.file_type
        }, context="audit")
    )
    db.add(event)
    
    # Update project updated_at
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.updated_at = func.now()
    
    db.commit()
    db.refresh(document)
    
    return DocumentResponse(
        id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        file_type=document.file_type,
        classification=document.classification.value,
        masked_text=document.masked_text,
        sanitize_level=document.sanitize_level.value,
        usage_restrictions=document.usage_restrictions,
        pii_gate_reasons=document.pii_gate_reasons,
        created_at=document.created_at
    )


@app.put("/api/projects/{project_id}/documents/{document_id}/sanitize", response_model=DocumentResponse)
async def re_sanitize_document(
    project_id: int,
    document_id: int,
    level: str = Query(default="strict", pattern="^(strict|paranoid)$"),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Re-sanitize a document to a higher sanitize_level.
    
    Deterministic, metadata-only operation:
    - Reads original text from file_path
    - Re-runs sanitization pipeline with specified level
    - Updates sanitize_level, masked_text, pii_gate_reasons, usage_restrictions
    - Never logs original text
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.project_id == project_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Read original text from file
    if not document.file_path or not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=400,
            detail="Original file not found. Cannot re-sanitize."
        )
    
    try:
        # Extract text from file
        if document.file_type == 'pdf':
            raw_text = extract_text_from_pdf(document.file_path)
        else:  # txt
            raw_text = extract_text_from_txt(document.file_path)
    except Exception as e:
        logger.error(f"Failed to extract text from {document.file_path}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to read original file"
        )
    
    # Normalize text
    normalized_text = normalize_text(raw_text)
    
    # Progressive sanitization pipeline
    pii_gate_reasons = {}
    sanitize_level = SanitizeLevel.NORMAL
    usage_restrictions = {"ai_allowed": True, "export_allowed": True}
    
    # Try normal masking first
    masked_text = mask_text(normalized_text, level="normal")
    is_safe, reasons = pii_gate_check(masked_text)
    if is_safe:
        sanitize_level = SanitizeLevel.NORMAL
        pii_gate_reasons = None
    else:
        pii_gate_reasons["normal"] = reasons
        
        # Try strict masking
        masked_text = mask_text(normalized_text, level="strict")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.STRICT
        else:
            pii_gate_reasons["strict"] = reasons
            
            # Use paranoid masking
            masked_text = mask_text(normalized_text, level="paranoid")
            sanitize_level = SanitizeLevel.PARANOID
    
    # Ensure we meet the requested level
    if level == "strict" and sanitize_level == SanitizeLevel.NORMAL:
        # Force strict level
        masked_text = mask_text(normalized_text, level="strict")
        sanitize_level = SanitizeLevel.STRICT
        # Re-check gate
        is_safe, reasons = pii_gate_check(masked_text)
        if not is_safe:
            # Must use paranoid
            masked_text = mask_text(normalized_text, level="paranoid")
            sanitize_level = SanitizeLevel.PARANOID
            usage_restrictions = {"ai_allowed": False, "export_allowed": False}
    
    # Update document
    document.masked_text = masked_text
    document.sanitize_level = sanitize_level
    document.pii_gate_reasons = pii_gate_reasons if pii_gate_reasons else None
    document.usage_restrictions = usage_restrictions
    
    # Create event (metadata only - never log original text)
    event = ProjectEvent(
        project_id=project_id,
        event_type="document_re_sanitized",
        actor=username,
        event_metadata=_safe_event_metadata({
            "document_id": document_id,
            "new_sanitize_level": sanitize_level.value,
            "file_type": document.file_type
        }, context="audit")
    )
    db.add(event)
    
    # Update project updated_at
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.updated_at = func.now()
    
    db.commit()
    db.refresh(document)
    
    return DocumentResponse(
        id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        file_type=document.file_type,
        classification=document.classification.value,
        masked_text=document.masked_text,
        sanitize_level=document.sanitize_level.value,
        usage_restrictions=document.usage_restrictions,
        pii_gate_reasons=document.pii_gate_reasons,
        created_at=document.created_at
    )


# Recordings endpoint
@app.post("/api/projects/{project_id}/recordings", response_model=DocumentListResponse, status_code=201)
async def upload_recording(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth),
    _: bool = Depends(rate_limit("upload", 20)),
):
    """
    Upload an audio recording and process it into a transcript document.
    Returns metadata only (no masked_text, no raw transcript).
    
    NEVER logs raw transcript or raw document content.
    """
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate file size (25MB max)
    file_content = await file.read()
    file_size = len(file_content)
    if file_size > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 25MB")
    
    # Audio received (metadata only; no filename)
    safe_ext = (os.path.splitext(file.filename or "")[1] or ".mp3").lower()
    logger.info(f"[AUDIO] Received: size_bytes={file_size} mime={file.content_type or 'unknown'} ext={safe_ext}")
    
    # Save audio file to permanent location (never exposed via API)
    audio_file_id = str(uuid.uuid4())
    audio_ext = safe_ext or '.mp3'
    audio_path = UPLOAD_DIR / f"{audio_file_id}{audio_ext}"
    
    try:
        with open(audio_path, 'wb') as f:
            f.write(file_content)
        logger.info(f"[AUDIO] Saved: ok doc_audio_id={audio_file_id}")
    except Exception as e:
        logger.error(f"[AUDIO] Failed to save audio file: err={type(e).__name__}")
        raise HTTPException(status_code=500, detail="Failed to save audio file")
    
    # Get file metadata (mime type, size)
    # Use actual content-type if available, fallback to application/octet-stream
    mime_type = file.content_type or "application/octet-stream"
    
    # Transcribe audio using configured STT engine (local or OpenAI)
    # NEVER log raw transcript
    logger.info("[AUDIO] Transcription starting")
    try:
        raw_transcript = transcribe_audio(str(audio_path))
        transcript_length = len(raw_transcript) if raw_transcript else 0
        logger.info(f"[AUDIO] Transcription finished: transcript_length={transcript_length}")
    except Exception as e:
        logger.error(f"[AUDIO] Transcription failed: err={type(e).__name__}")
        # Fail-closed: cleanup and raise error (no document created)
        if audio_path.exists():
            os.remove(audio_path)
        raise HTTPException(
            status_code=400,
            detail="Audio transcription failed"
        )
    
    # Normalize transcript text (deterministic post-processing)
    normalized_transcript = normalize_transcript_text(raw_transcript)
    normalized_length = len(normalized_transcript) if normalized_transcript else 0
    logger.info(f"[AUDIO] Transcript normalized: length={normalized_length}")
    
    # Get actual duration from transcription (if available)
    # For now, estimate from file size (can be improved with audio metadata)
    estimated_duration = None
    if file_size > 0:
        # Rough estimate: assume ~128kbps = ~1MB per minute
        estimated_duration = int((file_size / (1024 * 1024)) * 60)
    
    # Process transcript into structured format
    recording_date = datetime.now().strftime("%Y-%m-%d")
    processed_text = process_transcript(normalized_transcript, project.name, recording_date, estimated_duration)
    
    # Refine to editorial-ready first draft (deterministic)
    processed_text = refine_editorial_text(processed_text)
    
    # Create temporary TXT file with processed text
    temp_txt_path = UPLOAD_DIR / f"temp_transcript_{uuid.uuid4()}.txt"
    try:
        with open(temp_txt_path, 'w', encoding='utf-8') as f:
            f.write(processed_text)
    except Exception:
        # Cleanup audio file
        if audio_path.exists():
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail="Failed to create transcript file")
    
    # Feed processed text into existing ingest pipeline (same as TXT upload)
    try:
        # Normalize text
        normalized_text = normalize_text(processed_text)
        
        # Progressive sanitization pipeline (same as document upload)
        pii_gate_reasons = {}
        sanitize_level = SanitizeLevel.NORMAL
        usage_restrictions = {"ai_allowed": True, "export_allowed": True}
        masked_text = None
        
        # Try normal masking
        masked_text = mask_text(normalized_text, level="normal")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.NORMAL
            pii_gate_reasons = None
        else:
            pii_gate_reasons["normal"] = reasons
            
            # Try strict masking
            masked_text = mask_text(normalized_text, level="strict")
            is_safe, reasons = pii_gate_check(masked_text)
            if is_safe:
                sanitize_level = SanitizeLevel.STRICT
                usage_restrictions = {"ai_allowed": True, "export_allowed": True}
            else:
                pii_gate_reasons["strict"] = reasons
                
                # Use paranoid masking (must always pass gate)
                masked_text = mask_text(normalized_text, level="paranoid")
                is_safe, reasons = pii_gate_check(masked_text)
                
                if not is_safe:
                    # This should never happen - paranoid must guarantee gate pass
                    os.remove(temp_txt_path)
                    if audio_path.exists():
                        os.remove(audio_path)
                    raise HTTPException(
                        status_code=500,
                        detail="Internal error: Paranoid masking failed PII gate check. This is a bug."
                    )
                
                sanitize_level = SanitizeLevel.PARANOID
                usage_restrictions = {"ai_allowed": False, "export_allowed": False}
        
        # Move TXT file to permanent location
        txt_file_id = str(uuid.uuid4())
        permanent_txt_path = UPLOAD_DIR / f"{txt_file_id}.txt"
        shutil.move(str(temp_txt_path), str(permanent_txt_path))
        
        # Create document record (filename: rostmemo-{timestamp}.txt)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        document_filename = f"röstmemo-{timestamp}.txt"
        
        db_document = Document(
            project_id=project_id,
            filename=document_filename,
            file_type='txt',
            classification=project.classification,  # Inherit from project
            masked_text=masked_text,
            file_path=str(permanent_txt_path),  # Never exposed via API
            sanitize_level=sanitize_level,
            usage_restrictions=usage_restrictions,
            pii_gate_reasons=pii_gate_reasons if pii_gate_reasons else None
        )
        db.add(db_document)
        
        # Update project updated_at
        from sqlalchemy.sql import func
        project.updated_at = func.now()
        
        # Create event: recording_transcribed with ONLY metadata (no raw transcript)
        event_metadata = {
            "size": file_size,
            "mime": mime_type,
        }
        if estimated_duration:
            event_metadata["duration_seconds"] = estimated_duration
        # Store reference to audio file (non-exposed)
        event_metadata["recording_file_id"] = audio_file_id
        
        event = ProjectEvent(
            project_id=project_id,
            event_type="recording_transcribed",
            actor=username,
            event_metadata=_safe_event_metadata(event_metadata, context="audit")
        )
        db.add(event)
        
        logger.info("[AUDIO] Creating document")
        db.commit()
        db.refresh(db_document)
        logger.info(f"[AUDIO] Document created: id={db_document.id}")
        
        # Return metadata only (no masked_text, no raw transcript)
        return DocumentListResponse(
            id=db_document.id,
            project_id=db_document.project_id,
            filename=db_document.filename,
            file_type=db_document.file_type,
            classification=db_document.classification.value,
            sanitize_level=db_document.sanitize_level.value,
            usage_restrictions=db_document.usage_restrictions,
            pii_gate_reasons=db_document.pii_gate_reasons,
            created_at=db_document.created_at
        )
        
    except HTTPException:
        # Cleanup on error
        if temp_txt_path.exists():
            os.remove(temp_txt_path)
        if audio_path.exists():
            os.remove(audio_path)
        raise
    except Exception:
        # Cleanup on error
        if temp_txt_path.exists():
            os.remove(temp_txt_path)
        if audio_path.exists():
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail="Processing failed")


# ============================================================================
# Project Notes endpoints
# ============================================================================

@app.get("/api/projects/{project_id}/notes", response_model=List[NoteListResponse])
async def list_project_notes(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """List all notes for a project (metadata only, no masked_body)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    notes = db.query(ProjectNote).filter(ProjectNote.project_id == project_id).order_by(ProjectNote.created_at.desc()).all()
    return notes


@app.post("/api/projects/{project_id}/notes", response_model=NoteResponse, status_code=201)
async def create_note(
    project_id: int,
    note: NoteCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Create a note for a project.
    Body goes through same normalize/mask/sanitization pipeline as documents.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Normalize text
    normalized_text = normalize_text(note.body)
    
    # Progressive sanitization pipeline (same as documents)
    pii_gate_reasons = {}
    sanitize_level = SanitizeLevel.NORMAL
    
    # Try normal masking
    masked_text = mask_text(normalized_text, level="normal")
    is_safe, reasons = pii_gate_check(masked_text)
    if is_safe:
        sanitize_level = SanitizeLevel.NORMAL
        pii_gate_reasons = None
    else:
        pii_gate_reasons["normal"] = reasons
        
        # Try strict masking
        masked_text = mask_text(normalized_text, level="strict")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.STRICT
        else:
            pii_gate_reasons["strict"] = reasons
            
            # Use paranoid masking
            masked_text = mask_text(normalized_text, level="paranoid")
            sanitize_level = SanitizeLevel.PARANOID
    
    # Create note
    db_note = ProjectNote(
        project_id=project_id,
        title=note.title,
        masked_body=masked_text,
        sanitize_level=sanitize_level,
        pii_gate_reasons=pii_gate_reasons if pii_gate_reasons else None
    )
    db.add(db_note)
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=project_id,
        event_type="note_created",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": None,  # Will be set after commit
            "sanitize_level": sanitize_level.value
        }, context="audit")
    )
    db.add(event)
    
    db.commit()
    db.refresh(db_note)
    
    # Update event with note_id
    event.event_metadata["note_id"] = db_note.id
    db.commit()
    
    return db_note


@app.get("/api/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get a specific note with masked body."""
    note = db.query(ProjectNote).filter(ProjectNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@app.put("/api/projects/{project_id}/notes/{note_id}", response_model=NoteResponse)
async def update_project_note(
    project_id: int,
    note_id: int,
    note_update: NoteUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Update a project note.
    Body goes through same normalize/mask/sanitization pipeline as documents.
    """
    db_note = db.query(ProjectNote).filter(
        ProjectNote.id == note_id,
        ProjectNote.project_id == project_id
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Normalize text
    normalized_text = normalize_text(note_update.body)
    
    # Progressive sanitization pipeline (same as documents)
    pii_gate_reasons = {}
    sanitize_level = SanitizeLevel.NORMAL
    usage_restrictions = {"ai_allowed": True, "export_allowed": True}
    
    # Try normal masking
    masked_text = mask_text(normalized_text, level="normal")
    is_safe, reasons = pii_gate_check(masked_text)
    if is_safe:
        sanitize_level = SanitizeLevel.NORMAL
        pii_gate_reasons = None
    else:
        pii_gate_reasons["normal"] = reasons
        
        # Try strict masking
        masked_text = mask_text(normalized_text, level="strict")
        is_safe, reasons = pii_gate_check(masked_text)
        if is_safe:
            sanitize_level = SanitizeLevel.STRICT
        else:
            pii_gate_reasons["strict"] = reasons
            
            # Use paranoid masking
            masked_text = mask_text(normalized_text, level="paranoid")
            sanitize_level = SanitizeLevel.PARANOID
            usage_restrictions = {"ai_allowed": False, "export_allowed": False}
    
    # Update note
    if note_update.title is not None:
        db_note.title = note_update.title
    db_note.masked_body = masked_text
    db_note.sanitize_level = sanitize_level
    db_note.pii_gate_reasons = pii_gate_reasons if pii_gate_reasons else None
    db_note.usage_restrictions = usage_restrictions
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=project_id,
        event_type="note_updated",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": note_id,
            "note_type": "project_note"
        }, context="audit")
    )
    db.add(event)
    
    db.commit()
    db.refresh(db_note)
    
    return db_note

@app.delete("/api/notes/{note_id}", status_code=204)
async def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Delete a note."""
    note = db.query(ProjectNote).filter(ProjectNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    project_id = note.project_id
    db.delete(note)
    
    # Create deletion event
    event = ProjectEvent(
        project_id=project_id,
        event_type="note_deleted",
        actor=username,
        event_metadata=_safe_event_metadata({"note_id": note_id}, context="audit")
    )
    db.add(event)
    
    db.commit()
    return None


@app.put("/api/projects/{project_id}/notes/{note_id}/exclude-from-fortknox", response_model=NoteResponse)
async def exclude_note_from_fortknox(
    project_id: int,
    note_id: int,
    exclude: bool = Query(default=True),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Exkludera eller inkludera en anteckning från Fort Knox-sammanställningar.
    
    Metadata-only operation:
    - Uppdaterar usage_restrictions.fortknox_excluded
    - Loggar aldrig originaltext
    """
    db_note = db.query(ProjectNote).filter(
        ProjectNote.id == note_id,
        ProjectNote.project_id == project_id
    ).first()
    
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Update usage_restrictions
    if not db_note.usage_restrictions:
        db_note.usage_restrictions = {}
    
    db_note.usage_restrictions['fortknox_excluded'] = exclude
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=project_id,
        event_type="note_fortknox_exclusion_changed",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": note_id,
            "excluded": exclude
        }, context="audit")
    )
    db.add(event)
    
    db.commit()
    db.refresh(db_note)
    
    return db_note


@app.put("/api/projects/{project_id}/notes/{note_id}/sanitize", response_model=NoteResponse)
async def re_sanitize_note(
    project_id: int,
    note_id: int,
    level: str = Query(default="strict", pattern="^(strict|paranoid)$"),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Re-sanitize a note to a higher sanitize_level.
    
    Note: Notes don't store original text, only masked_body.
    This endpoint attempts to upgrade sanitize_level but cannot re-process original text.
    Returns error if original text is required but not available.
    """
    db_note = db.query(ProjectNote).filter(
        ProjectNote.id == note_id,
        ProjectNote.project_id == project_id
    ).first()
    
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Notes don't store original text - we can't re-sanitize properly
    # Return error explaining this limitation
    raise HTTPException(
        status_code=400,
        detail=(
            "Notes cannot be re-sanitized because original text is not stored. "
            "Please edit the note manually to update sanitization level."
        )
    )


# Journalist Notes endpoints
# ============================================================================

@app.get("/api/projects/{project_id}/journalist-notes", response_model=List[JournalistNoteListResponse])
async def list_journalist_notes(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """List all journalist notes for a project (metadata only, no body)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    notes = db.query(JournalistNote).filter(JournalistNote.project_id == project_id).order_by(JournalistNote.updated_at.desc()).all()
    
    # Build list response with preview (title or first line of body)
    result = []
    for note in notes:
        # Use title if available, otherwise first line of body
        if note.title:
            preview = note.title
        else:
            preview = note.body.split('\n')[0] if note.body else ""
            if len(preview) > 100:
                preview = preview[:100] + "..."
        
        result.append(JournalistNoteListResponse(
            id=note.id,
            project_id=note.project_id,
            title=note.title,
            preview=preview,
            category=note.category.value,
            created_at=note.created_at,
            updated_at=note.updated_at
        ))
    
    return result


@app.get("/api/journalist-notes/{note_id}", response_model=JournalistNoteResponse)
async def get_journalist_note(
    note_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get a specific journalist note with raw body."""
    note = db.query(JournalistNote).filter(JournalistNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.get("/api/journalist-notes/{note_id}/images", response_model=List[JournalistNoteImageResponse])
async def list_journalist_note_images(
    note_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """List all images for a journalist note."""
    note = db.query(JournalistNote).filter(JournalistNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    images = (
        db.query(JournalistNoteImage)
        .filter(JournalistNoteImage.note_id == note_id)
        .order_by(JournalistNoteImage.created_at.desc())
        .all()
    )
    return images


@app.post("/api/projects/{project_id}/journalist-notes", response_model=JournalistNoteResponse, status_code=201)
async def create_journalist_note(
    project_id: int,
    note: JournalistNoteCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Create a journalist note.
    Only technical sanitization (no masking, no normalization, no AI).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Technical sanitization only (no masking, no normalization)
    sanitized_body = sanitize_journalist_note(note.body)
    
    # Sanitize title if provided
    sanitized_title = None
    if note.title:
        sanitized_title = sanitize_journalist_note(note.title).strip()
        if not sanitized_title:
            sanitized_title = None
    
    # Create note
    db_note = JournalistNote(
        project_id=project_id,
        title=sanitized_title,
        body=sanitized_body,
        category=note.category or NoteCategory.RAW
    )
    db.add(db_note)
    
    # Create event (metadata only - NEVER content)
    event = ProjectEvent(
        project_id=project_id,
        event_type="note_created",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": None,  # Will be set after commit
            "note_type": "journalist"
        }, context="audit")
    )
    db.add(event)
    
    db.commit()
    db.refresh(db_note)
    
    # Update event with note_id
    event.event_metadata["note_id"] = db_note.id
    db.commit()
    
    return db_note


@app.put("/api/journalist-notes/{note_id}", response_model=JournalistNoteResponse)
async def update_journalist_note(
    note_id: int,
    note: JournalistNoteUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Update a journalist note.
    Only technical sanitization (no masking, no normalization, no AI).
    """
    db_note = db.query(JournalistNote).filter(JournalistNote.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Technical sanitization only
    sanitized_body = sanitize_journalist_note(note.body)
    
    # Sanitize title if provided
    if note.title is not None:
        sanitized_title = sanitize_journalist_note(note.title).strip()
        db_note.title = sanitized_title if sanitized_title else None
    # If title is not provided in update, keep existing title
    
    db_note.body = sanitized_body
    
    # Update category if provided
    if note.category is not None:
        db_note.category = note.category
    
    # updated_at is set automatically by onupdate
    
    # Create event (metadata only)
    event = ProjectEvent(
        project_id=db_note.project_id,
        event_type="note_updated",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": note_id,
            "note_type": "journalist"
        }, context="audit")
    )
    db.add(event)
    
    # Update project updated_at
    from sqlalchemy.sql import func
    project = db.query(Project).filter(Project.id == db_note.project_id).first()
    if project:
        project.updated_at = func.now()
    
    db.commit()
    db.refresh(db_note)
    
    return db_note


@app.delete("/api/journalist-notes/{note_id}", status_code=204)
async def delete_journalist_note(
    note_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Delete a journalist note and associated images."""
    note = db.query(JournalistNote).filter(JournalistNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    project_id = note.project_id
    
    # Delete associated images from disk
    images = db.query(JournalistNoteImage).filter(JournalistNoteImage.note_id == note_id).all()
    for image in images:
        image_path = UPLOAD_DIR / image.file_path
        if image_path.exists():
            try:
                os.remove(image_path)
            except Exception:
                pass  # Ignore errors
    
    # Delete note (cascade will delete images from DB)
    db.delete(note)
    
    # Create deletion event
    event = ProjectEvent(
        project_id=project_id,
        event_type="note_deleted",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": note_id,
            "note_type": "journalist"
        }, context="audit")
    )
    db.add(event)
    
    db.commit()
    return None


@app.get("/api/projects/{project_id}/export")
async def export_project_markdown(
    project_id: int,
    include_metadata: bool = Query(True),
    include_transcripts: bool = Query(False),
    include_notes: bool = Query(False),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Export project as Markdown. Notes OFF by default for privacy."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Fetch data
    documents = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at).all()
    transcripts = db.query(ProjectNote).filter(ProjectNote.project_id == project_id).order_by(ProjectNote.created_at).all()
    sources = db.query(ProjectSource).filter(ProjectSource.project_id == project_id).order_by(ProjectSource.created_at).all()
    journalist_notes = db.query(JournalistNote).filter(JournalistNote.project_id == project_id).order_by(JournalistNote.created_at).all()
    
    # Build Markdown (follow template exactly)
    md = f"# Projekt: {project.name}\n\n"
    
    # Project metadata (only if include_metadata=true)
    if include_metadata:
        md += f"Projekt-ID: {project.id}\n"
        md += f"Status: {project.status.value}\n"
        md += f"Skapad: {project.created_at.strftime('%Y-%m-%d')}\n"
        md += f"Uppdaterad: {project.updated_at.strftime('%Y-%m-%d')}\n\n"
    else:
        md += "\n"
    
    # Export settings
    md += "## Exportinställningar\n\n"
    md += f"Inkludera metadata: {include_metadata}\n"
    md += f"Inkludera röstmemo/transkript: {include_transcripts}\n"
    md += f"Inkludera anteckningar: {include_notes}\n"
    if include_metadata:
        md += f"Skapad av: {username}\n"
    md += f"Exportdatum: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    
    # Sources (only if include_metadata=true)
    md += "## Källor\n\n"
    if include_metadata:
        md += "(Detta är metadata som journalisten manuellt har lagt till.)\n\n"
        type_labels = {"link": "Länk", "person": "Person", "document": "Dokument", "other": "Övrigt"}
        if sources:
            for src in sources:
                type_label = type_labels.get(src.type.value, src.type.value)
                md += f"**{type_label}** — {src.title}\n"
                if src.comment:
                    md += f"Kommentar: {src.comment}\n"
                md += f"Skapad: {src.created_at.strftime('%Y-%m-%d')}\n\n"
        else:
            md += "*(Inget att visa)*\n\n"
    else:
        md += "*(Ej inkluderat i denna export)*\n\n"
    
    # Documents (always included)
    md += "## Dokument\n\n"
    if documents:
        for doc in documents:
            md += f"### {doc.filename}\n\n"
            if include_metadata:
                md += f"Dokument-ID: {doc.id}\n"
            md += f"Skapad: {doc.created_at.strftime('%Y-%m-%d')}\n\n"
            md += f"{doc.masked_text}\n\n"
    else:
        md += "*(Inget att visa)*\n\n"
    
    # Transcripts (only if toggled)
    md += "## Röstmemo / Transkript\n\n"
    if include_transcripts:
        if transcripts:
            for trans in transcripts:
                title = trans.title if trans.title else "Namnlöst transkript"
                md += f"### {title}\n\n"
                if include_metadata:
                    md += f"Transkript-ID: {trans.id}\n"
                md += f"Skapad: {trans.created_at.strftime('%Y-%m-%d')}\n\n"
                md += f"{trans.masked_body}\n\n"
        else:
            md += "*(Inget att visa)*\n\n"
    else:
        md += "*(Ej inkluderat i denna export)*\n\n"
    
    # Notes (only if explicitly toggled, OFF by default)
    md += "## Anteckningar\n\n"
    if include_notes:
        if journalist_notes:
            for note in journalist_notes:
                title = note.title if note.title else "Namnlös anteckning"
                md += f"### {title}\n\n"
                if include_metadata:
                    md += f"Antecknings-ID: {note.id}\n"
                    md += f"Kategori: {note.category.value}\n"
                md += f"Skapad: {note.created_at.strftime('%Y-%m-%d')}\n"
                md += f"Uppdaterad: {note.updated_at.strftime('%Y-%m-%d')}\n\n"
                md += f"{note.body}\n\n"
        else:
            md += "*(Inget att visa)*\n\n"
    else:
        md += "*(Ej inkluderat i denna export)*\n\n"
    
    # Footer
    md += "---\n\n"
    md += "## Integritetsnotis\n\n"
    md += "Denna export kan innehålla sanerat material från dokument och (om valt) transkript.\n"
    md += "Privata anteckningar inkluderas inte som standard.\n"
    md += "Systemets events/loggar innehåller aldrig innehåll, endast metadata.\n"
    
    # Log event (metadata only, NO CONTENT)
    event_metadata = _safe_event_metadata({
        "format": "markdown",
        "include_metadata": include_metadata,
        "include_transcripts": include_transcripts,
        "include_notes": include_notes
    }, context="audit")
    
    event = ProjectEvent(
        project_id=project_id,
        event_type="export_created",
        actor=username,
        event_metadata=event_metadata
    )
    db.add(event)
    db.commit()
    
    logger.info(f"Project {project_id} exported (format=markdown, notes={include_notes}, transcripts={include_transcripts})")
    
    # Return as downloadable file
    filename = f"project_{project_id}_export.md"
    return PlainTextResponse(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/journalist-notes/{note_id}/images", response_model=JournalistNoteImageResponse, status_code=201)
async def upload_journalist_note_image(
    note_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Upload an image to a journalist note.
    Images are private references only - no analysis, no OCR, no AI.
    """
    note = db.query(JournalistNote).filter(JournalistNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Validate file size (10MB max)
    file_content = await file.read()
    file_size = len(file_content)
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 10MB")
    
    # Validate image format
    mime_type = file.content_type or ""
    if not mime_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Create directory for note images
    note_images_dir = UPLOAD_DIR / "journalist_notes" / str(note_id)
    note_images_dir.mkdir(parents=True, exist_ok=True)
    
    # Save image
    image_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1] or '.jpg'
    image_path = note_images_dir / f"{image_id}{file_ext}"
    
    try:
        with open(image_path, 'wb') as f:
            f.write(file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")
    
    # Create image record
    db_image = JournalistNoteImage(
        note_id=note_id,
        file_path=f"journalist_notes/{note_id}/{image_id}{file_ext}",  # Relative path
        filename=file.filename,
        mime_type=mime_type
    )
    db.add(db_image)
    
    # Create event (metadata only - NEVER image content)
    event = ProjectEvent(
        project_id=note.project_id,
        event_type="note_image_added",
        actor=username,
        event_metadata=_safe_event_metadata({
            "note_id": note_id,
            "image_id": None,  # Will be set after commit
            "mime_type": mime_type,
            "size": file_size
        }, context="audit")
    )
    db.add(event)
    
    db.commit()
    db.refresh(db_image)
    
    # Update event with image_id
    event.event_metadata["image_id"] = db_image.id
    db.commit()
    
    return db_image


@app.get("/api/journalist-notes/{note_id}/images/{image_id}")
async def get_journalist_note_image(
    note_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get an image file for inline display."""
    note = db.query(JournalistNote).filter(JournalistNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    image = db.query(JournalistNoteImage).filter(
        JournalistNoteImage.id == image_id,
        JournalistNoteImage.note_id == note_id
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image_path = UPLOAD_DIR / image.file_path
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(image_path),
        media_type=image.mime_type,
        filename=image.filename
    )


# ===== PROJECT SOURCES ENDPOINTS =====

@app.post("/api/projects/{project_id}/sources", response_model=ProjectSourceResponse, status_code=201)
async def create_project_source(
    project_id: int,
    source_data: ProjectSourceCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Create a new source/reference for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create source
    source = ProjectSource(
        project_id=project_id,
        title=source_data.title,
        type=source_data.type,
        url=getattr(source_data, 'url', None),
        comment=source_data.comment
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    # Log event (metadata only: type + timestamp, NO title/comment)
    event_metadata = _safe_event_metadata({
        "type": source_data.type.value
    }, context="audit")
    
    event = ProjectEvent(
        project_id=project_id,
        event_type="source_added",
        actor=username,
        event_metadata=event_metadata
    )
    db.add(event)
    db.commit()
    
    logger.info(f"Source added to project {project_id}: type={source_data.type.value}")
    
    return source


@app.get("/api/projects/{project_id}/sources", response_model=List[ProjectSourceResponse])
async def get_project_sources(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Get all sources for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    sources = db.query(ProjectSource).filter(ProjectSource.project_id == project_id).order_by(ProjectSource.created_at.desc()).all()
    return sources

@app.put("/api/projects/{project_id}/sources/{source_id}", response_model=ProjectSourceResponse)
async def update_project_source(
    project_id: int,
    source_id: int,
    source_update: ProjectSourceUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Update a project source."""
    source = db.query(ProjectSource).filter(
        ProjectSource.id == source_id,
        ProjectSource.project_id == project_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Update fields if provided
    if source_update.title is not None:
        source.title = source_update.title
    if source_update.type is not None:
        source.type = source_update.type
    if source_update.url is not None:
        source.url = source_update.url
    if source_update.comment is not None:
        source.comment = source_update.comment
    
    db.commit()
    db.refresh(source)
    
    # Log update event
    event = ProjectEvent(
        project_id=project_id,
        event_type="source_updated",
        actor=username,
        event_metadata=_safe_event_metadata({
            "source_id": source_id,
            "source_type": source.type.value if hasattr(source.type, 'value') else str(source.type)
        }, context="audit")
    )
    db.add(event)
    db.commit()
    
    return source


@app.delete("/api/projects/{project_id}/sources/{source_id}", status_code=204)
async def delete_project_source(
    project_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Delete a source (hard delete)."""
    source = db.query(ProjectSource).filter(
        ProjectSource.id == source_id,
        ProjectSource.project_id == project_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source_type = source.type.value
    
    # Delete source
    db.delete(source)
    db.commit()
    
    # Log event (metadata only: type, NO title/comment)
    event_metadata = _safe_event_metadata({
        "type": source_type
    }, context="audit")
    
    event = ProjectEvent(
        project_id=project_id,
        event_type="source_removed",
        actor=username,
        event_metadata=event_metadata
    )
    db.add(event)
    db.commit()
    
    logger.info(f"Source removed from project {project_id}: type={source_type}")
    
    return None


# Scout endpoints
@app.get("/api/scout/feeds", response_model=List[ScoutFeedResponse])
async def list_scout_feeds(
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """List all Scout feeds. Lazy seed: creates default feeds if table is empty."""
    # Lazy seed: if no feeds exist, create defaults
    feed_count = db.query(ScoutFeed).count()
    if feed_count == 0:
        defaults = [
            ScoutFeed(
                name="Polisen – Händelser Västra Götaland",
                url="https://polisen.se/aktuellt/rss/vastra-gotaland/handelser-rss---vastra-gotaland/",
                is_enabled=True
            ),
            ScoutFeed(
                name="Polisen – Pressmeddelanden Västra Götaland",
                url="https://polisen.se/aktuellt/rss/vastra-gotaland/pressmeddelanden-rss---vastra-gotaland/",
                is_enabled=True
            ),
            ScoutFeed(
                name="Göteborgs tingsrätt",
                url="https://www.domstol.se/feed/56/?searchPageId=1139&scope=news",
                is_enabled=True
            )
        ]
        for feed in defaults:
            db.add(feed)
        db.commit()
        logger.info("Scout: Created 3 default feeds (all enabled)")
    else:
        # Kontrollera om Göteborgs tingsrätt feed saknas och lägg till den
        domstol_feed = db.query(ScoutFeed).filter(
            ScoutFeed.url == "https://www.domstol.se/feed/56/?searchPageId=1139&scope=news"
        ).first()
        if not domstol_feed:
            new_feed = ScoutFeed(
                name="Göteborgs tingsrätt",
                url="https://www.domstol.se/feed/56/?searchPageId=1139&scope=news",
                is_enabled=True
            )
            db.add(new_feed)
            db.commit()
            logger.info("Scout: Added Göteborgs tingsrätt feed to existing feeds")
    
    feeds = db.query(ScoutFeed).all()
    return feeds


@app.post("/api/scout/feeds", response_model=ScoutFeedResponse, status_code=201)
async def create_scout_feed(
    feed_data: ScoutFeedCreate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Create a new Scout feed."""
    feed = ScoutFeed(
        name=feed_data.name,
        url=feed_data.url,
        is_enabled=True
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


@app.delete("/api/scout/feeds/{feed_id}", status_code=204)
async def delete_scout_feed(
    feed_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    username: str = Depends(verify_basic_auth)
):
    """Disable a Scout feed (soft delete)."""
    feed = db.query(ScoutFeed).filter(ScoutFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    feed.is_enabled = False
    db.commit()
    return None


@app.put("/api/scout/feeds/{feed_id}", response_model=ScoutFeedResponse)
async def update_scout_feed(
    feed_id: int,
    body: ScoutFeedUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Update a Scout feed (name/url) or toggle enabled state."""
    feed = db.query(ScoutFeed).filter(ScoutFeed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    if body.name is not None:
        feed.name = body.name
    if body.url is not None:
        feed.url = body.url
    if body.is_enabled is not None:
        feed.is_enabled = body.is_enabled

    db.commit()
    db.refresh(feed)
    return feed


@app.get("/api/scout/items", response_model=List[ScoutItemResponse])
async def list_scout_items(
    # Domstolsflöden publicerar ofta mer sällan än 7 dagar.
    # Vi tillåter längre lookback men begränsar fortfarande med limit för prestanda.
    hours: int = Query(24, ge=1, le=8760),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """List Scout items from last N hours."""
    from datetime import timedelta
    from sqlalchemy import func as sql_func
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Filter: (published_at >= cutoff) OR (published_at IS NULL AND fetched_at >= cutoff)
    items = db.query(ScoutItem).filter(
        or_(
            ScoutItem.published_at >= cutoff,
            and_(ScoutItem.published_at.is_(None), ScoutItem.fetched_at >= cutoff)
        )
    ).order_by(
        sql_func.coalesce(ScoutItem.published_at, ScoutItem.fetched_at).desc()
    ).limit(limit).all()
    
    return items


@app.post("/api/scout/fetch")
async def fetch_scout_feeds(
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """Manually trigger RSS feed fetch."""
    from scout import fetch_all_feeds

    # Seeda default-feeds om tabellen är tom (UI kan kalla /fetch utan att någonsin kalla /feeds)
    feed_count = db.query(ScoutFeed).count()
    if feed_count == 0:
        defaults = [
            ScoutFeed(
                name="Polisen – Händelser Västra Götaland",
                url="https://polisen.se/aktuellt/rss/vastra-gotaland/handelser-rss---vastra-gotaland/",
                is_enabled=True
            ),
            ScoutFeed(
                name="Polisen – Pressmeddelanden Västra Götaland",
                url="https://polisen.se/aktuellt/rss/vastra-gotaland/pressmeddelanden-rss---vastra-gotaland/",
                is_enabled=True
            ),
            ScoutFeed(
                name="Göteborgs tingsrätt",
                url="https://www.domstol.se/feed/56/?searchPageId=1139&scope=news",
                is_enabled=True
            )
        ]
        for feed in defaults:
            db.add(feed)
        db.commit()
        logger.info("Scout: Created 3 default feeds (all enabled) [seeded in /fetch]")
    
    results = fetch_all_feeds(db)
    return {"feeds_processed": len(results), "results": results}


@app.get("/api/projects/{project_id}/fortknox/reports", response_model=List[KnoxReportResponse])
async def list_fortknox_reports(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Lista alla Fort Knox-rapporter för ett projekt.
    
    Returns:
        Lista av KnoxReportResponse (metadata + rendered_markdown)
    """
    # Verifiera att projektet finns
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Hämta alla rapporter för projektet
    reports = db.query(KnoxReport).filter(
        KnoxReport.project_id == project_id
    ).order_by(KnoxReport.created_at.desc()).all()
    
    return [
        KnoxReportResponse(
            id=report.id,
            project_id=report.project_id,
            policy_id=report.policy_id,
            policy_version=report.policy_version,
            ruleset_hash=report.ruleset_hash,
            template_id=report.template_id,
            engine_id=report.engine_id,
            input_fingerprint=report.input_fingerprint,
            input_manifest=report.input_manifest,
            gate_results=report.gate_results,
            rendered_markdown=report.rendered_markdown,
            created_at=report.created_at,
            latency_ms=report.latency_ms
        )
        for report in reports
    ]


@app.get("/api/fortknox/reports/{report_id}", response_model=KnoxReportResponse)
async def get_fortknox_report(
    report_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Hämta en specifik Fort Knox-rapport.
    
    Returns:
        KnoxReportResponse (metadata + rendered_markdown)
    """
    report = db.query(KnoxReport).filter(KnoxReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Knox report not found")
    
    return KnoxReportResponse(
        id=report.id,
        project_id=report.project_id,
        policy_id=report.policy_id,
        policy_version=report.policy_version,
        ruleset_hash=report.ruleset_hash,
        template_id=report.template_id,
        engine_id=report.engine_id,
        input_fingerprint=report.input_fingerprint,
        input_manifest=report.input_manifest,
        gate_results=report.gate_results,
        rendered_markdown=report.rendered_markdown,
        created_at=report.created_at,
        latency_ms=report.latency_ms
    )


# ===== FEED IMPORT ENDPOINTS =====

@app.get("/api/feeds/preview", response_model=FeedPreviewResponse)
async def preview_feed(
    url: str = Query(..., description="Feed URL to preview"),
    username: str = Depends(verify_basic_auth)
):
    """
    Preview a feed without creating a project.
    Returns feed metadata and items (no storage).
    """
    from feeds import fetch_feed_url, parse_feed
    
    try:
        # Fetch and validate URL (SSRF protection)
        content = fetch_feed_url(url)
        
        # Parse feed
        feed_data = parse_feed(content)
        
        # Convert to response format
        items = [
            FeedItemPreview(
                guid=item['guid'],
                title=item['title'],
                link=item['link'],
                published=item['published'],
                summary_text=item['summary_text']
            )
            for item in feed_data['items']
        ]
        
        return FeedPreviewResponse(
            title=feed_data['title'],
            description=feed_data['description'],
            items=items
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Feed preview failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to preview feed: {str(e)}")


@app.post("/api/projects/from-feed", response_model=CreateProjectFromFeedResponse, status_code=201)
async def create_project_from_feed(
    request: CreateProjectFromFeedRequest,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Create a project from a feed URL.
    Creates Project with description/tags, ProjectSource with URL, ProjectNote with fulltext,
    and Document - all using the same ingest pipeline.
    """
    from feeds import fetch_feed_url, parse_feed, fetch_article_text, derive_tags
    import hashlib
    
    try:
        # Fetch and parse feed
        content = fetch_feed_url(request.url)
        feed_data = parse_feed(content)
        
        # Determine project name
        project_name = request.project_name or feed_data['title'] or "Feed Import"
        
        # Derive tags
        tags = derive_tags(feed_data['title'], request.url)
        
        # Create project description
        description = f"Imported from RSS feed: {feed_data['title']}. Feed URL: {request.url}"
        
        # Check if project with same name already exists
        db_project = db.query(Project).filter(Project.name == project_name).first()
        
        if not db_project:
            # Create new project
            db_project = Project(
                name=project_name,
                description=description,
                classification=Classification.NORMAL,
                status=ProjectStatus.RESEARCH,
                tags=tags
            )
            db.add(db_project)
            db.commit()
            db.refresh(db_project)
            
            # Create initial event
            event = ProjectEvent(
                project_id=db_project.id,
                event_type="project_created",
                actor=username,
                event_metadata=_safe_event_metadata({"name": project_name, "source": "feed_import"}, context="audit")
            )
            db.add(event)
            db.commit()
        else:
            # Update existing project description/tags if needed
            if not db_project.description or "Imported from RSS" not in db_project.description:
                db_project.description = description
            if not db_project.tags:
                db_project.tags = tags
            db.commit()
        
        # Process feed items
        created_documents = 0
        created_notes = 0
        created_sources = 0
        skipped_duplicates = 0
        items_to_process = feed_data['items'][:request.limit]
        
        for item in items_to_process:
            item_guid = item.get('guid') or None
            item_link = item.get('link') or ''
            
            # Dedupe: check if document with same guid or link already exists in project
            existing_doc = None
            if item_guid:
                # Check by guid first (PostgreSQL JSONB query)
                from sqlalchemy import func
                existing_doc = db.query(Document).filter(
                    Document.project_id == db_project.id,
                    Document.document_metadata.isnot(None),
                    func.jsonb_extract_path_text(Document.document_metadata, 'item_guid') == item_guid
                ).first()
            
            if not existing_doc and item_link:
                # Check by link if guid didn't match
                existing_doc = db.query(Document).filter(
                    Document.project_id == db_project.id,
                    Document.document_metadata.isnot(None),
                    func.jsonb_extract_path_text(Document.document_metadata, 'item_link') == item_link
                ).first()
            
            if existing_doc:
                skipped_duplicates += 1
                continue
            
            # Fetch article text (fulltext or summary)
            article_text = ""
            mode = request.mode or "fulltext"  # Default to fulltext if not specified
            logger.info(f"Processing item with mode={mode}, link={item_link}")
            
            if mode == "fulltext" and item_link:
                logger.info(f"Fetching fulltext for item: {item_link}")
                try:
                    article_text = fetch_article_text(item_link)
                    logger.info(f"Fetched article text length: {len(article_text)} chars")
                except Exception as e:
                    logger.error(f"Failed to fetch article text: {e}")
                    article_text = ""
            
            # Fallback to summary if fulltext is empty
            if not article_text:
                logger.warning(f"Fulltext extraction returned empty, using summary for: {item_link}")
                article_text = item.get('summary_text', '')
                logger.info(f"Using summary text length: {len(article_text)} chars")
            
            # Build raw content with better formatting
            published_str = item.get('published') or ''
            published_display = ""
            if published_str:
                try:
                    from datetime import datetime
                    # Try to parse ISO format
                    dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    published_display = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    published_display = published_str
            
            feed_title = feed_data.get('title', 'RSS Feed')
            
            if article_text:
                raw_content = f"""KÄLLA
{feed_title}
{item_link}

PUBLICERAD
{published_display}

INNEHÅLL
{article_text}

EXTRAKTION
Källa hämtad via RSS + artikellänk
Text extraherad automatiskt"""
            else:
                raw_content = f"""KÄLLA
{feed_title}
{item_link}

PUBLICERAD
{published_display}

INNEHÅLL
{item.get('summary_text', '')}

EXTRAKTION
Källa hämtad via RSS (endast sammanfattning)"""
            
            # Run sanitize pipeline (fail-closed)
            try:
                pipeline_result = run_sanitize_pipeline(raw_content)
            except Exception as e:
                logger.error(f"Pipeline failed for feed item {item_link}: {e}")
                continue  # Skip this item (fail-closed)

            # Feed/Scout är systemgenererat underlag. För att Extern inte ska fastna i
            # sanitize_level_too_low direkt så höjer vi miniminivån till STRICT deterministiskt.
            # OBS: Inga råa texter loggas.
            try:
                if pipeline_result.get("sanitize_level") == SanitizeLevel.NORMAL:
                    normalized = normalize_text(raw_content)
                    strict_masked = mask_text(normalized, level="strict")
                    # Maska datum/tid för strict
                    strict_masked, datetime_stats = mask_datetime(strict_masked, level="strict")
                    is_safe, reasons = pii_gate_check(strict_masked)
                    if is_safe:
                        pipeline_result["masked_text"] = strict_masked
                        pipeline_result["sanitize_level"] = SanitizeLevel.STRICT
                        pipeline_result["pii_gate_reasons"] = None
                        pipeline_result["usage_restrictions"] = {"ai_allowed": True, "export_allowed": True}
                        pipeline_result["datetime_masked"] = datetime_stats["datetime_masked"]
                        pipeline_result["datetime_mask_count"] = datetime_stats["datetime_mask_count"]
                    else:
                        paranoid_masked = mask_text(normalized, level="paranoid")
                        # Maska datum/tid för paranoid
                        paranoid_masked, datetime_stats_p = mask_datetime(paranoid_masked, level="paranoid")
                        is_safe_p, reasons_p = pii_gate_check(paranoid_masked)
                        if not is_safe_p:
                            raise Exception("Paranoid masking failed PII gate for feed item")
                        pipeline_result["masked_text"] = paranoid_masked
                        pipeline_result["sanitize_level"] = SanitizeLevel.PARANOID
                        pipeline_result["pii_gate_reasons"] = {"strict": reasons, "paranoid": reasons_p}
                        pipeline_result["usage_restrictions"] = {"ai_allowed": False, "export_allowed": False}
                        pipeline_result["datetime_masked"] = datetime_stats_p["datetime_masked"]
                        pipeline_result["datetime_mask_count"] = datetime_stats_p["datetime_mask_count"]
            except Exception as e:
                logger.error(f"Failed to enforce min strict for feed item {item_link}: {e}")
                continue  # Skip item (fail-closed)
            
            # Generate filename from item title (sanitized for filesystem)
            # Use item title as filename, fallback to guid/hash
            if item.get('title'):
                # Sanitize title for filename: remove special chars, limit length
                import re
                # Keep word chars, spaces, hyphens, and Swedish chars
                safe_title = re.sub(r'[^\w\s\-åäöÅÄÖ]', '', item['title'])
                safe_title = re.sub(r'\s+', '_', safe_title.strip())
                safe_title = safe_title[:100]  # Limit length
                filename = f"{safe_title}.txt"
            elif item_guid:
                filename = f"feed_{item_guid[:8]}.txt"
            else:
                # Hash link for stable filename
                link_hash = hashlib.sha256(item_link.encode()).hexdigest()[:8]
                filename = f"feed_{link_hash}.txt"
            
            # Create file on disk (required by Document model)
            file_id = str(uuid.uuid4())
            permanent_path = UPLOAD_DIR / f"{file_id}.txt"
            try:
                with open(permanent_path, 'w', encoding='utf-8') as f:
                    f.write(raw_content)
            except Exception as e:
                logger.error(f"Failed to create file for feed item: {str(e)}")
                continue
            
            # Create Document
            doc_metadata = {
                "source_type": "feed",
                "feed_url": request.url,
                "feed_title": feed_data['title'],
                "item_guid": item_guid,
                "item_link": item_link,
                "published": published_str
            }
            
            db_document = Document(
                project_id=db_project.id,
                filename=filename,
                file_type="txt",
                classification=Classification.NORMAL,
                masked_text=pipeline_result["masked_text"],
                file_path=str(permanent_path),
                sanitize_level=pipeline_result["sanitize_level"],
                usage_restrictions=pipeline_result["usage_restrictions"],
                pii_gate_reasons=pipeline_result["pii_gate_reasons"],
                document_metadata=doc_metadata
            )
            db.add(db_document)
            db.flush()  # Get document ID
            
            created_documents += 1
            
            # Create ProjectSource (dedupe on URL)
            existing_source = db.query(ProjectSource).filter(
                ProjectSource.project_id == db_project.id,
                ProjectSource.url == item_link
            ).first()
            
            if not existing_source and item_link:
                db_source = ProjectSource(
                    project_id=db_project.id,
                    title=item['title'],
                    type=SourceType.LINK,
                    url=item_link,
                    comment="Imported from RSS"
                )
                db.add(db_source)
                created_sources += 1
            
            # Create ProjectNote
            db_note = ProjectNote(
                project_id=db_project.id,
                title=item['title'],
                masked_body=pipeline_result["masked_text"],
                sanitize_level=pipeline_result["sanitize_level"],
                pii_gate_reasons=pipeline_result["pii_gate_reasons"],
                usage_restrictions=pipeline_result["usage_restrictions"]
            )
            db.add(db_note)
            created_notes += 1
            
            # Commit after each item (or batch commit - but safer per-item for now)
            db.commit()
        
        # Log import event (metadata only)
        import_event = ProjectEvent(
            project_id=db_project.id,
            event_type="feed_imported",
            actor=username,
            event_metadata=_safe_event_metadata({
                "feed_url": request.url,
                "created_documents": created_documents,
                "created_notes": created_notes,
                "created_sources": created_sources,
                "skipped_duplicates": skipped_duplicates,
                "limit": request.limit
            }, context="audit")
        )
        db.add(import_event)
        db.commit()
        
        logger.info(f"Feed import completed: project_id={db_project.id}, documents={created_documents}, notes={created_notes}, sources={created_sources}, skipped={skipped_duplicates}")
        
        return CreateProjectFromFeedResponse(
            project_id=db_project.id,
            created_count=created_documents,
            created_notes=created_notes,
            created_sources=created_sources,
            skipped_duplicates=skipped_duplicates
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Feed import failed: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to import feed: {str(e)}")


@app.post("/api/projects/from-scout-item", response_model=CreateProjectFromScoutItemResponse, status_code=201)
async def create_project_from_scout_item(
    request: CreateProjectFromScoutItemRequest,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Create a project from a single Scout item.
    Creates a project with the item's title and imports the item as a document.
    """
    from text_processing import normalize_text, mask_text, pii_gate_check
    
    try:
        # Get Scout item
        scout_item = db.query(ScoutItem).filter(ScoutItem.id == request.scout_item_id).first()
        if not scout_item:
            raise HTTPException(status_code=404, detail="Scout item not found")
        
        # Get feed URL from ScoutFeed
        scout_feed = db.query(ScoutFeed).filter(ScoutFeed.id == scout_item.feed_id).first()
        feed_url = scout_feed.url if scout_feed else None
        
        # Determine project name
        project_name = request.project_name or scout_item.title[:200]  # Limit length
        
        # Create new project
        db_project = Project(
            name=project_name,
            description=f"Skapad från Scout: {scout_item.raw_source}",
            classification=Classification.NORMAL,
            status=ProjectStatus.RESEARCH
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        
        # Create initial event
        event = ProjectEvent(
            project_id=db_project.id,
            event_type="project_created",
            actor=username,
            event_metadata=_safe_event_metadata({
                "name": project_name,
                "source": "scout_item",
                "scout_item_id": request.scout_item_id
            }, context="audit")
        )
        db.add(event)
        
        # Fetch fulltext from article link if available
        article_text = ""
        if scout_item.link:
            logger.info(f"Fetching fulltext for scout item: {scout_item.link}")
            try:
                from feeds import fetch_article_text
                article_text = fetch_article_text(scout_item.link)
                logger.info(f"Fetched article text length: {len(article_text)} chars")
            except Exception as e:
                logger.warning(f"Failed to fetch article text: {e}")
                article_text = ""
        
        # Build raw content from Scout item with better formatting
        published_str = scout_item.published_at.isoformat() if scout_item.published_at else ""
        published_display = ""
        if scout_item.published_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                published_display = dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                published_display = published_str
        
        if article_text:
            raw_content = f"""KÄLLA
{scout_item.raw_source or 'Scout Feed'}
{scout_item.link}

PUBLICERAD
{published_display}

INNEHÅLL
{article_text}

EXTRAKTION
Källa hämtad via RSS + artikellänk
Text extraherad automatiskt (Scout)"""
        else:
            raw_content = f"""KÄLLA
{scout_item.raw_source or 'Scout Feed'}
{scout_item.link}

PUBLICERAD
{published_display}

EXTRAKTION
Källa hämtad via RSS (endast sammanfattning)"""
        
        # Run ingest pipeline (same as document upload)
        try:
            pipeline_result = run_sanitize_pipeline(raw_content)
        except Exception as e:
            logger.error(f"Pipeline failed for scout item {scout_item.link}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to process content: {str(e)}")
        
        masked_text = pipeline_result["masked_text"]
        sanitize_level = pipeline_result["sanitize_level"]
        pii_gate_reasons = pipeline_result["pii_gate_reasons"]
        usage_restrictions = pipeline_result["usage_restrictions"]
        datetime_masked = pipeline_result.get("datetime_masked", False)
        datetime_mask_count = pipeline_result.get("datetime_mask_count", 0)

        # Scout är systemgenererat underlag. För att undvika att Extern blir en återvändsgränd
        # (sanitize_level_too_low direkt) så höjer vi miniminivån till STRICT deterministiskt.
        # OBS: Vi använder endast råtexten i minnet här (inget loggas, inget sparas rått).
        if sanitize_level == SanitizeLevel.NORMAL:
            normalized = normalize_text(raw_content)
            strict_masked = mask_text(normalized, level="strict")
            # Maska datum/tid för strict
            strict_masked, datetime_stats = mask_datetime(strict_masked, level="strict")
            is_safe, reasons = pii_gate_check(strict_masked)
            if is_safe:
                masked_text = strict_masked
                sanitize_level = SanitizeLevel.STRICT
                # pii_gate_reasons är None om normal passerade; behåll None här.
                pii_gate_reasons = None
                usage_restrictions = {"ai_allowed": True, "export_allowed": True}
                datetime_masked = datetime_stats["datetime_masked"]
                datetime_mask_count = datetime_stats["datetime_mask_count"]
            else:
                # Fail-closed: paranoid ska alltid passera gate
                paranoid_masked = mask_text(normalized, level="paranoid")
                # Maska datum/tid för paranoid
                paranoid_masked, datetime_stats_p = mask_datetime(paranoid_masked, level="paranoid")
                is_safe_p, reasons_p = pii_gate_check(paranoid_masked)
                if not is_safe_p:
                    raise HTTPException(status_code=500, detail="Internal error: Paranoid masking failed PII gate for Scout item")
                masked_text = paranoid_masked
                sanitize_level = SanitizeLevel.PARANOID
                pii_gate_reasons = {"strict": reasons, "paranoid": reasons_p}
                usage_restrictions = {"ai_allowed": False, "export_allowed": False}
                datetime_masked = datetime_stats_p["datetime_masked"]
                datetime_mask_count = datetime_stats_p["datetime_mask_count"]
        
        # Generate filename from scout item title (sanitized for filesystem)
        import re
        if scout_item.title:
            # Keep word chars, spaces, hyphens, and Swedish chars
            safe_title = re.sub(r'[^\w\s\-åäöÅÄÖ]', '', scout_item.title)
            safe_title = re.sub(r'\s+', '_', safe_title.strip())
            safe_title = safe_title[:100]  # Limit length
            filename = f"{safe_title}.txt"
        else:
            filename = f"scout_item_{scout_item.id}.txt"
        
        # Create document from Scout item
        db_document = Document(
            project_id=db_project.id,
            filename=filename,
            file_type="txt",
            classification=db_project.classification,
            masked_text=masked_text,
            file_path=f"scout_import_{uuid.uuid4()}.txt",  # Placeholder, no actual file storage
            sanitize_level=sanitize_level,
            usage_restrictions=usage_restrictions,
            pii_gate_reasons=pii_gate_reasons if pii_gate_reasons else None,
            document_metadata={
                "source_type": "scout_item",
                "scout_item_id": scout_item.id,
                "scout_feed_id": scout_item.feed_id,
                "feed_url": feed_url,
                "item_link": scout_item.link,
                "item_guid": scout_item.guid_hash,
                "published": published_str,
                "raw_source": scout_item.raw_source,
                # Metadata-only: använd för UI-badge (Datum maskat) utan att logga/spara råtext
                "datetime_masked": bool(datetime_masked),
                "datetime_mask_count": int(datetime_mask_count or 0),
            }
        )
        db.add(db_document)
        
        # Create ProjectSource
        db_source = ProjectSource(
            project_id=db_project.id,
            title=scout_item.raw_source or "Scout Feed",
            type=SourceType.LINK,
            url=scout_item.link,
            comment="RSS-import via Scout"
        )
        db.add(db_source)
        
        # Create ProjectNote with fulltext
        db_note = ProjectNote(
            project_id=db_project.id,
            title=scout_item.title,
            masked_body=masked_text,
            sanitize_level=sanitize_level,
            pii_gate_reasons=pii_gate_reasons if pii_gate_reasons else None,
            usage_restrictions=usage_restrictions
        )
        db.add(db_note)
        
        db.commit()
        db.refresh(db_document)
        
        return CreateProjectFromScoutItemResponse(
            project_id=db_project.id,
            document_id=db_document.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project from scout item {request.scout_item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project from scout item: {str(e)}")


# ============================================================================
# Fort Knox endpoints
# ============================================================================

@app.get("/api/projects/{project_id}/export_snapshot")
async def export_project_snapshot(
    project_id: int,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Deterministiskt snapshot av projektets underlag för Fort Knox External.
    Returnerar:
      - export_markdown: säkert (maskat) markdown-underlag
      - input_manifest: [{type, id, title, sanitize_level, created_at, updated_at}]
      - counts: {documents, notes, sources, transcripts}
    Inga råa original. Endast sanerat innehåll och metadata.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at.asc(), Document.id.asc()).all()
    # Exkludera Fort Knox-genererade rapportdokument från snapshot-underlag
    # (annars riskerar vi recursion/quote-gate och sämre UX).
    documents = [
        d for d in documents
        if not (getattr(d, "document_metadata", None) and (d.document_metadata or {}).get("source_type") == "fortknox_report")
    ]
    notes = db.query(ProjectNote).filter(ProjectNote.project_id == project_id).order_by(ProjectNote.created_at.asc(), ProjectNote.id.asc()).all()
    sources = db.query(ProjectSource).filter(ProjectSource.project_id == project_id).order_by(ProjectSource.created_at.asc(), ProjectSource.id.asc()).all()
    transcripts = []  # TODO: iteration 2

    input_manifest: List[Dict[str, Any]] = []
    for doc in documents:
        # can_autofix: vi kan bumpa deterministiskt så länge masked_text finns.
        # Scout-importerade dokument kan sakna fysisk fil, men masked_text finns i DB och räcker.
        can_autofix = bool((doc.masked_text or "").strip())
        blocking_reason = None if can_autofix else "ORIGINAL_MISSING"
        # datetime_masked: check om [DATUM] eller [TID] tokens finns (metadata-only)
        masked_content = doc.masked_text or ""
        datetime_masked = ("[DATUM]" in masked_content or "[TID]" in masked_content or "[RELATIV_TID]" in masked_content)
        input_manifest.append({
            "type": "document",
            "id": doc.id,
            "title": doc.filename,
            "sanitize_level": getattr(doc.sanitize_level, "value", str(doc.sanitize_level)),
            "created_at": doc.created_at.isoformat(),
            "updated_at": (getattr(doc, "updated_at", None) or doc.created_at).isoformat(),
            "origin": "scout" if getattr(doc, "document_metadata", None) and getattr(doc, "document_metadata").get("raw_source") else "manual",
            "can_autofix": can_autofix,
            "blocking_reason": blocking_reason,
            "datetime_masked": datetime_masked
        })
    for note in notes:
        # Heuristik utan schemaändring:
        # - AUTO (Scout/Feed) skapas av importflöden och får oftast usage_restrictions satt
        # - MANUAL (användarskapad) saknar ofta usage_restrictions
        origin = "scout" if getattr(note, "usage_restrictions", None) else "manual"
        can_autofix = bool((note.masked_body or "").strip())
        # datetime_masked: check om [DATUM] eller [TID] tokens finns (metadata-only)
        masked_content = note.masked_body or ""
        datetime_masked = ("[DATUM]" in masked_content or "[TID]" in masked_content or "[RELATIV_TID]" in masked_content)
        input_manifest.append({
            "type": "note",
            "id": note.id,
            "title": note.title or f"Anteckning {note.id}",
            "sanitize_level": getattr(note.sanitize_level, "value", str(note.sanitize_level)),
            "created_at": note.created_at.isoformat(),
            "updated_at": (getattr(note, "updated_at", None) or note.created_at).isoformat(),
            "origin": origin,
            "can_autofix": can_autofix,
            "blocking_reason": None if can_autofix else "EMPTY_MASKED_BODY",
            "datetime_masked": datetime_masked
        })

    md_lines: List[str] = []
    md_lines.append(f"# Fort Knox Export Snapshot — Projekt {project.name}")
    md_lines.append("")
    md_lines.append(f"Genererad: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md_lines.append("")
    md_lines.append("## Dokument")
    md_lines.append("")
    if documents:
        for doc in documents:
            md_lines.append(f"### {doc.filename} (id: {doc.id})")
            md_lines.append("")
            md_lines.append(doc.masked_text or "")
            md_lines.append("")
    else:
        md_lines.append("*(Inga dokument)*")
        md_lines.append("")
    md_lines.append("## Anteckningar")
    md_lines.append("")
    if notes:
        for note in notes:
            title = note.title or f"Anteckning {note.id}"
            md_lines.append(f"### {title} (id: {note.id})")
            md_lines.append("")
            md_lines.append(note.masked_body or "")
            md_lines.append("")
    else:
        md_lines.append("*(Inga anteckningar)*")
        md_lines.append("")

    export_markdown = "\n".join(md_lines)
    counts = {
        "documents": len(documents),
        "notes": len(notes),
        "sources": len(sources),
        "transcripts": len(transcripts)
    }
    return {
        "export_markdown": export_markdown,
        "input_manifest": input_manifest,
        "counts": counts
    }

@app.post("/api/fortknox/compile", response_model=KnoxReportResponse, status_code=201)
async def compile_fortknox_report(
    request: KnoxCompileRequest,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth),
    _: bool = Depends(rate_limit("fortknox_compile", 6)),
):
    """
    Kompilera Fort Knox-rapport från projekt.
    
    Pipeline:
    1. Bygg KnoxInputPack (deterministiskt)
    2. Input Gate (sanitize level + PII gate + size check)
    3. Idempotens Check (om rapport redan finns, returnera den)
    4. Remote URL Check (om saknas → FORTKNOX_OFFLINE)
    5. Remote Call (eller test mode)
    6. Output Gate + Re-ID Guard
    7. Spara KnoxReport
    """
    import time
    start_time = time.time()
    
    try:
        # Hämta policy
        policy = get_policy(request.policy_id)
        
        # 1. Bygg KnoxInputPack
        pack = build_knox_input_pack(
            project_id=request.project_id,
            policy=policy,
            template_id=request.template_id,
            db=db
        )

        # 1.2. Om selection/snapshot_mode: applicera urval deterministiskt (iteration 1: documents + notes)
        if request.snapshot_mode or (request.selection is not None):
            include_docs = set()
            include_notes = set()
            exclude_docs = set()
            exclude_notes = set()
            if request.selection:
                for item in (request.selection.include or []):
                    if item.type == "document":
                        include_docs.add(item.id)
                    elif item.type == "note":
                        include_notes.add(item.id)
                for item in (request.selection.exclude or []):
                    if item.type == "document":
                        exclude_docs.add(item.id)
                    elif item.type == "note":
                        exclude_notes.add(item.id)
            # Om include-listor finns -> använd endast dessa, annars alla
            current_doc_ids = {d.doc_id for d in pack.documents}
            current_note_ids = {n.note_id for n in pack.notes}
            if include_docs:
                final_doc_ids = include_docs & current_doc_ids
            else:
                final_doc_ids = set(current_doc_ids)
            if include_notes:
                final_note_ids = include_notes & current_note_ids
            else:
                final_note_ids = set(current_note_ids)
            # Applicera exclude
            final_doc_ids -= exclude_docs
            final_note_ids -= exclude_notes
            # Filtrera items
            new_documents = [d for d in pack.documents if d.doc_id in final_doc_ids]
            new_notes = [n for n in pack.notes if n.note_id in final_note_ids]
            # Kontroll: tomt urval
            if len(new_documents) + len(new_notes) == 0:
                logger.warning(
                    "Fort Knox compile: Empty selection set",
                    extra={
                        "project_id": request.project_id,
                        "policy_id": request.policy_id,
                        "template_id": request.template_id
                    }
                )
                raise HTTPException(
                    status_code=400,
                    detail=KnoxErrorResponse(
                        error_code="EMPTY_INPUT_SET",
                        reasons=["Du har exkluderat allt underlag. Välj minst ett dokument eller en anteckning."],
                        detail="Selection produced empty input set"
                    ).model_dump()
                )
            # Bygg nytt manifest: dokument + anteckningar + befintliga sources från pack
            new_manifest: List[Dict[str, Any]] = []
            for d in new_documents:
                new_manifest.append({
                    "kind": "document",
                    "id": d.doc_id,
                    "sha256": d.sha256,
                    "sanitize_level": d.sanitize_level,
                    "updated_at": d.updated_at.isoformat() if hasattr(d.updated_at, "isoformat") else d.updated_at
                })
            for n in new_notes:
                new_manifest.append({
                    "kind": "note",
                    "id": n.note_id,
                    "sha256": n.sha256,
                    "sanitize_level": n.sanitize_level,
                    "updated_at": n.updated_at.isoformat() if hasattr(n.updated_at, "isoformat") else n.updated_at
                })
            # Lägg till sources från tidigare manifest (behåll metadata)
            for m in pack.input_manifest:
                if m.get("kind") == "source":
                    new_manifest.append(m)
            # Sortera manifest deterministiskt
            new_manifest = sorted(new_manifest, key=lambda x: (x.get("kind",""), x.get("id", 0)))
            # Re-fingerprint
            manifest_json = canonical_json(new_manifest)
            new_fingerprint = compute_sha256(manifest_json)
            # Uppdatera pack (pydantic-modell är muterbar)
            pack.documents = new_documents
            pack.notes = new_notes
            pack.input_manifest = new_manifest
            pack.input_fingerprint = new_fingerprint
        
        # 1.5. Validera att input set inte är tomt (efter exkludering)
        total_inputs = len(pack.documents) + len(pack.notes) + len(pack.sources)
        if total_inputs == 0:
            logger.warning(
                "Fort Knox compile: Empty input set after exclusion",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id
                }
            )
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="EMPTY_INPUT_SET",
                    reasons=["Alla dokument, anteckningar och källor är exkluderade från sammanställningen"],
                    detail="Input set is empty after exclusion"
                ).model_dump()
        )
        
        # 2. Input Gate
        input_pass, input_reasons = input_gate(pack, policy)
        if not input_pass:
            logger.warning(
                "Fort Knox compile: Input gate failed",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id,
                    "reasons": input_reasons
                }
            )
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="INPUT_GATE_FAILED",
                    reasons=input_reasons,
                    detail="Input gate validation failed"
                ).model_dump()
            )
        
        # 3. Idempotens Check (före remote URL-check)
        #
        # IMPORTANT:
        # Vi måste inkludera "vilken motor" som användes i cache-nyckeln,
        # annars kan en gammal TESTMODE-fixture återanvändas när man byter till live (lokal LLM).
        test_mode = os.getenv("FORTKNOX_TESTMODE", "0") == "1"
        engine_id_current = "test_mode" if test_mode else os.getenv("FORTKNOX_ENGINE_ID", "remote")
        engine_id_current = (engine_id_current or "").strip() or ("test_mode" if test_mode else "remote")

        existing_report = db.query(KnoxReport).filter(
            KnoxReport.project_id == request.project_id,
            KnoxReport.policy_id == request.policy_id,
            KnoxReport.template_id == request.template_id,
            KnoxReport.input_fingerprint == pack.input_fingerprint,
            KnoxReport.engine_id == engine_id_current
        ).first()
        
        if existing_report:
            logger.info(
                "Fort Knox compile: Returning existing report (idempotency)",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id,
                    "report_id": existing_report.id,
                    "input_fingerprint": pack.input_fingerprint
                }
            )
            # Returnera befintlig rapport (även om remote offline)
            return KnoxReportResponse(
                id=existing_report.id,
                project_id=existing_report.project_id,
                policy_id=existing_report.policy_id,
                policy_version=existing_report.policy_version,
                ruleset_hash=existing_report.ruleset_hash,
                template_id=existing_report.template_id,
                engine_id=existing_report.engine_id,
                input_fingerprint=existing_report.input_fingerprint,
                input_manifest=existing_report.input_manifest,
                gate_results=existing_report.gate_results,
                rendered_markdown=existing_report.rendered_markdown,
                created_at=existing_report.created_at,
                latency_ms=existing_report.latency_ms
            )
        
        # 4. Remote URL Check (endast om inte test mode)
        remote_url = os.getenv("FORTKNOX_REMOTE_URL", "").strip()
        
        if not test_mode and not remote_url:
            logger.warning(
                "Fort Knox compile: FORTKNOX_REMOTE_URL not set",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id
                }
            )
            raise HTTPException(
                status_code=503,
                detail=KnoxErrorResponse(
                    error_code="FORTKNOX_OFFLINE",
                    reasons=["remote_url_not_configured"],
                    detail="FORTKNOX_REMOTE_URL not set"
                ).model_dump()
            )
        
        # 5. Remote Call
        try:
            # I test mode, remote_url kan vara tomt (compile_remote hanterar test mode)
            llm_response = compile_remote(
                pack=pack,
                policy=policy,
                template_id=request.template_id,
                remote_url=remote_url if remote_url else "http://test"  # Dummy URL för test mode
            )
        except FortKnoxRemoteError as e:
            logger.error(
                f"Fort Knox compile: Remote error: {e.error_code}",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id,
                    "error_code": e.error_code,
                    "reasons": e.reasons
                }
            )
            raise HTTPException(
                status_code=500,
                detail=KnoxErrorResponse(
                    error_code="REMOTE_ERROR",
                    reasons=e.reasons,
                    detail=e.detail
                ).model_dump()
            )
        
        # 6. Output Gate + Re-ID Guard (kontrollerar llm output)
        # Gör outputen först för att kunna skriva integritetsstatus i rapporten
        rendered_text_candidate = render_markdown(llm_response.model_dump(), request.template_id)
        
        # Samla input texts för re-ID guard
        input_texts = [doc.masked_text for doc in pack.documents] + [note.masked_body for note in pack.notes]
        
        # PII gate check på rendered markdown
        is_safe, pii_reasons = pii_gate_check(rendered_text_candidate)
        output_gate_reasons = []
        if not is_safe:
            output_gate_reasons.extend([f"pii_gate_{reason}" for reason in pii_reasons])
        
        # Re-ID Guard
        re_id_pass, re_id_reasons = re_id_guard(rendered_text_candidate, input_texts, policy)
        if not re_id_pass:
            output_gate_reasons.extend(re_id_reasons)
        
        # Fail-closed: om output gate fail, spara ingen rapport
        if output_gate_reasons:
            logger.warning(
                "Fort Knox compile: Output gate failed",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id,
                    "reasons": output_gate_reasons
                }
            )
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="OUTPUT_GATE_FAILED",
                    reasons=output_gate_reasons,
                    detail="Output gate validation failed"
                ).model_dump()
            )
        
        # 7. Bygg slutlig rendered_markdown enligt specifik struktur (svenska)
        # Sektioner:
        # Sammanställning
        # 1. Vad vi vet just nu
        # 2. Det här behöver vi verifiera
        # 3. Tidslinje
        # 4. Underlag som ingick
        # 5. Risker och integritet
        # 6. Rekommenderade nästa steg
        # Bilaga: Audit
        llm_json = llm_response.model_dump()
        lines: List[str] = []
        # Titel (används även som filnamn vid export till dokument)
        report_title = (llm_json.get("title") or "Rapport").strip()
        lines.append(f"# {report_title}")
        lines.append("")
        # Sammanställning
        lines.append("## Sammanställning")
        lines.append("")
        if llm_json.get("executive_summary"):
            lines.append(llm_json["executive_summary"])
        else:
            lines.append("Sammanställningen bygger på valt underlag. Inga personuppgifter eller råtexter exponeras i denna rapport.")
        lines.append("")
        # 1. Vad vi vet just nu
        lines.append("## 1. Vad vi vet just nu")
        lines.append("")
        themes = llm_json.get("themes") or []
        theme_bullets = []
        for theme in themes:
            theme_bullets.extend(theme.get("bullets", []))
        if theme_bullets:
            for bullet in theme_bullets[:7]:
                lines.append(f"- {bullet}")
        else:
            lines.append("- Inga tydliga observationer kunde extraheras från underlaget.")
        lines.append("")
        # 2. Det här behöver vi verifiera
        lines.append("## 2. Det här behöver vi verifiera")
        lines.append("")
        open_q = llm_json.get("open_questions") or []
        if open_q:
            for q in open_q[:7]:
                lines.append(f"- {q}")
        else:
            lines.append("- Inga specifika verifieringspunkter identifierades.")
        lines.append("")
        # 3. Tidslinje
        lines.append("## 3. Tidslinje")
        lines.append("")
        tl = llm_json.get("timeline_high_level") or []
        if tl:
            for t in tl:
                lines.append(f"- {t}")
        else:
            lines.append("Ingen tydlig tidslinje i valt material")
        lines.append("")
        # 4. Underlag som ingick (max 10 rader)
        lines.append("## 4. Underlag som ingick (utan PII)")
        lines.append("")
        # Använd pack.input_manifest som är filtrerat via selection om tillämpat
        manifest = pack.input_manifest or []
        listed = 0
        for m in manifest:
            if m.get("kind") in ("document", "note"):
                type_label = "Dokument" if m["kind"] == "document" else "Anteckning"
                lines.append(f"- [{type_label}] {m.get('id')} (sanitize: {m.get('sanitize_level')})")
                listed += 1
                if listed >= 10:
                    break
        remaining = sum(1 for m in manifest if m.get("kind") in ("document","note")) - listed
        if remaining > 0:
            lines.append(f"(+{remaining} fler)")
        lines.append("")
        # 5. Risker och integritet
        lines.append("## 5. Risker och integritet")
        lines.append("")
        lines.append("Inga tecken på PII i output och re-ID guard passerade utan varningar.")
        lines.append("")
        # 6. Rekommenderade nästa steg
        lines.append("## 6. Rekommenderade nästa steg")
        lines.append("")
        next_steps = llm_json.get("next_steps") or []
        if next_steps:
            for step in next_steps[:7]:
                lines.append(f"- {step}")
        else:
            lines.append("- Inga explicita nästa steg identifierade.")
        lines.append("")
        # Bilaga: Audit
        lines.append("## Bilaga: Audit")
        lines.append("")
        lines.append(f"Policy: {policy.policy_id} v{policy.policy_version}")
        lines.append(f"Ruleset: {policy.ruleset_hash}")
        lines.append(f"Ingångsfingerprint: {pack.input_fingerprint[:16]}...")
        lines.append("")
        final_rendered_markdown = "\n".join(lines)
        
        # 7b. Output gate på final markdown (fail-closed)
        final_candidate = final_rendered_markdown
        is_safe, pii_reasons = pii_gate_check(final_candidate)
        output_gate_reasons = []
        if not is_safe:
            output_gate_reasons.extend([f"pii_gate_{reason}" for reason in pii_reasons])

        re_id_pass, re_id_reasons = re_id_guard(final_candidate, input_texts, policy)
        if (not re_id_pass) and ("quote_detected" in re_id_reasons):
            # Försök bryta n-gram-overlap deterministiskt (External showreel-säkerhet)
            final_candidate, _breaks = break_quote_ngrams(final_candidate, input_texts, policy, max_breaks=12)
            re_id_pass, re_id_reasons = re_id_guard(final_candidate, input_texts, policy)
        if not re_id_pass:
            output_gate_reasons.extend(re_id_reasons)

        if output_gate_reasons:
            logger.warning(
                "Fort Knox compile: Output gate failed (final)",
                extra={
                    "project_id": request.project_id,
                    "policy_id": request.policy_id,
                    "template_id": request.template_id,
                    "reasons": output_gate_reasons
                }
            )
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="OUTPUT_GATE_FAILED",
                    reasons=output_gate_reasons,
                    detail="Output gate validation failed"
                ).model_dump()
            )

        final_rendered_markdown = final_candidate

        # 8. Spara KnoxReport
        latency_ms = int((time.time() - start_time) * 1000)
        
        gate_results = {
            "input": {"pass": True, "reasons": []},
            "output": {"pass": True, "reasons": []}
        }
        
        db_report = KnoxReport(
            project_id=request.project_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            ruleset_hash=policy.ruleset_hash,
            template_id=request.template_id,
            engine_id=engine_id_current,
            input_fingerprint=pack.input_fingerprint,
            input_manifest=pack.input_manifest,
            gate_results=gate_results,
            rendered_markdown=final_rendered_markdown,
            latency_ms=latency_ms
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
        
        logger.info(
            "Fort Knox compile: Success",
            extra={
                "project_id": request.project_id,
                "policy_id": request.policy_id,
                "template_id": request.template_id,
                "report_id": db_report.id,
                "input_fingerprint": pack.input_fingerprint,
                "latency_ms": latency_ms
            }
        )
        
        return KnoxReportResponse(
            id=db_report.id,
            project_id=db_report.project_id,
            policy_id=db_report.policy_id,
            policy_version=db_report.policy_version,
            ruleset_hash=db_report.ruleset_hash,
            template_id=db_report.template_id,
            engine_id=db_report.engine_id,
            input_fingerprint=db_report.input_fingerprint,
            input_manifest=db_report.input_manifest,
            gate_results=db_report.gate_results,
            rendered_markdown=db_report.rendered_markdown,
            created_at=db_report.created_at,
            latency_ms=db_report.latency_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Fort Knox compile: Unexpected error: {e}",
            extra={
                "project_id": request.project_id,
                "policy_id": request.policy_id,
                "template_id": request.template_id
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=KnoxErrorResponse(
                error_code="INTERNAL_ERROR",
                reasons=["unexpected_error"],
                detail=str(e)
            ).model_dump()
        )


@app.post("/api/fortknox/compile/langchain", response_model=KnoxReportResponse, status_code=201)
async def compile_fortknox_report_langchain(
    request: KnoxCompileRequest,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth),
    _: bool = Depends(rate_limit("fortknox_compile", 6)),
):
    """
    Opt-in LangChain pipeline for Fort Knox.
    - Default AV (styrt av env FORTKNOX_PIPELINE=langchain).
    - Håller befintlig /api/fortknox/compile orörd (regressionsäker).
    """
    import time
    start_time = time.time()

    try:
        policy = get_policy(request.policy_id)

        # Bygg pack deterministiskt
        pack = build_knox_input_pack(
            project_id=request.project_id,
            policy=policy,
            template_id=request.template_id,
            db=db
        )

        # Samma selection/snapshot_mode-logik som standard compile
        if request.snapshot_mode or (request.selection is not None):
            include_docs = set()
            include_notes = set()
            exclude_docs = set()
            exclude_notes = set()
            if request.selection:
                for item in (request.selection.include or []):
                    if item.type == "document":
                        include_docs.add(item.id)
                    elif item.type == "note":
                        include_notes.add(item.id)
                for item in (request.selection.exclude or []):
                    if item.type == "document":
                        exclude_docs.add(item.id)
                    elif item.type == "note":
                        exclude_notes.add(item.id)

            current_doc_ids = {d.doc_id for d in pack.documents}
            current_note_ids = {n.note_id for n in pack.notes}
            final_doc_ids = (include_docs & current_doc_ids) if include_docs else set(current_doc_ids)
            final_note_ids = (include_notes & current_note_ids) if include_notes else set(current_note_ids)
            final_doc_ids -= exclude_docs
            final_note_ids -= exclude_notes

            new_documents = [d for d in pack.documents if d.doc_id in final_doc_ids]
            new_notes = [n for n in pack.notes if n.note_id in final_note_ids]
            if len(new_documents) + len(new_notes) == 0:
                raise HTTPException(
                    status_code=400,
                    detail=KnoxErrorResponse(
                        error_code="EMPTY_INPUT_SET",
                        reasons=["Du har exkluderat allt underlag. Välj minst ett dokument eller en anteckning."],
                        detail="Selection produced empty input set"
                    ).model_dump()
                )

            new_manifest: List[Dict[str, Any]] = []
            for d in new_documents:
                new_manifest.append({
                    "kind": "document",
                    "id": d.doc_id,
                    "sha256": d.sha256,
                    "sanitize_level": d.sanitize_level,
                    "updated_at": d.updated_at.isoformat() if hasattr(d.updated_at, "isoformat") else d.updated_at
                })
            for n in new_notes:
                new_manifest.append({
                    "kind": "note",
                    "id": n.note_id,
                    "sha256": n.sha256,
                    "sanitize_level": n.sanitize_level,
                    "updated_at": n.updated_at.isoformat() if hasattr(n.updated_at, "isoformat") else n.updated_at
                })
            for m in pack.input_manifest:
                if m.get("kind") == "source":
                    new_manifest.append(m)
            new_manifest = sorted(new_manifest, key=lambda x: (x.get("kind", ""), x.get("id", 0)))
            manifest_json = canonical_json(new_manifest)
            new_fingerprint = compute_sha256(manifest_json)
            pack.documents = new_documents
            pack.notes = new_notes
            pack.input_manifest = new_manifest
            pack.input_fingerprint = new_fingerprint

        # Input set check
        total_inputs = len(pack.documents) + len(pack.notes) + len(pack.sources)
        if total_inputs == 0:
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="EMPTY_INPUT_SET",
                    reasons=["Alla dokument, anteckningar och källor är exkluderade från sammanställningen"],
                    detail="Input set is empty after exclusion"
                ).model_dump()
            )

        # Input gate
        input_pass, input_reasons = input_gate(pack, policy)
        if not input_pass:
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="INPUT_GATE_FAILED",
                    reasons=input_reasons,
                    detail="Input gate validation failed"
                ).model_dump()
            )

        # Idempotens (separerad engine_id)
        engine_id_current = "langchain"
        existing_report = db.query(KnoxReport).filter(
            KnoxReport.project_id == request.project_id,
            KnoxReport.policy_id == policy.policy_id,
            KnoxReport.template_id == request.template_id,
            KnoxReport.engine_id == engine_id_current,
            KnoxReport.input_fingerprint == pack.input_fingerprint,
        ).order_by(KnoxReport.created_at.desc(), KnoxReport.id.desc()).first()
        if existing_report:
            return KnoxReportResponse(
                id=existing_report.id,
                project_id=existing_report.project_id,
                policy_id=existing_report.policy_id,
                policy_version=existing_report.policy_version,
                ruleset_hash=existing_report.ruleset_hash,
                template_id=existing_report.template_id,
                engine_id=existing_report.engine_id,
                input_fingerprint=existing_report.input_fingerprint,
                input_manifest=existing_report.input_manifest,
                gate_results=existing_report.gate_results,
                rendered_markdown=existing_report.rendered_markdown,
                created_at=existing_report.created_at,
                latency_ms=existing_report.latency_ms
            )

        # LangChain compile (fail-closed)
        try:
            llm_response, llm_latency_ms = compile_with_langchain(pack, policy, request.template_id)
        except FortKnoxLangChainConfigError as e:
            raise HTTPException(
                status_code=409,
                detail=KnoxErrorResponse(
                    error_code="LANGCHAIN_DISABLED",
                    reasons=["langchain_not_enabled_or_configured"],
                    detail=str(e)
                ).model_dump()
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=KnoxErrorResponse(
                    error_code="REMOTE_ERROR",
                    reasons=["langchain_llm_error"],
                    detail=type(e).__name__
                ).model_dump()
            )

        # Render candidate för output gate
        rendered_text_candidate = render_markdown(llm_response.model_dump(), request.template_id)
        input_texts = [doc.masked_text for doc in pack.documents] + [note.masked_body for note in pack.notes]
        is_safe, pii_reasons = pii_gate_check(rendered_text_candidate)
        output_gate_reasons = []
        if not is_safe:
            output_gate_reasons.extend([f"pii_gate_{reason}" for reason in pii_reasons])
        re_id_pass, re_id_reasons = re_id_guard(rendered_text_candidate, input_texts, policy)
        if not re_id_pass:
            output_gate_reasons.extend(re_id_reasons)
        if output_gate_reasons:
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="OUTPUT_GATE_FAILED",
                    reasons=output_gate_reasons,
                    detail="Output gate validation failed"
                ).model_dump()
            )

        # Bygg slutlig rapport (samma struktur som standardvägen)
        llm_json = llm_response.model_dump()
        lines: List[str] = []
        report_title = (llm_json.get("title") or "Rapport").strip()
        lines.append(f"# {report_title}")
        lines.append("")
        lines.append("## Sammanställning")
        lines.append("")
        if llm_json.get("executive_summary"):
            lines.append(llm_json["executive_summary"])
        else:
            lines.append("Sammanställningen bygger på valt underlag. Inga personuppgifter eller råtexter exponeras i denna rapport.")
        lines.append("")
        lines.append("## 1. Vad vi vet just nu")
        lines.append("")
        themes = llm_json.get("themes") or []
        theme_bullets = []
        for theme in themes:
            theme_bullets.extend(theme.get("bullets", []))
        if theme_bullets:
            for bullet in theme_bullets[:7]:
                lines.append(f"- {bullet}")
        else:
            lines.append("- Inga tydliga observationer kunde extraheras från underlaget.")
        lines.append("")
        lines.append("## 2. Det här behöver vi verifiera")
        lines.append("")
        open_q = llm_json.get("open_questions") or []
        if open_q:
            for q in open_q[:7]:
                lines.append(f"- {q}")
        else:
            lines.append("- Inga specifika verifieringspunkter identifierades.")
        lines.append("")
        lines.append("## 3. Tidslinje")
        lines.append("")
        tl = llm_json.get("timeline_high_level") or []
        if tl:
            for t in tl:
                lines.append(f"- {t}")
        else:
            lines.append("Ingen tydlig tidslinje i valt material")
        lines.append("")
        lines.append("## 4. Underlag som ingick (utan PII)")
        lines.append("")
        manifest = pack.input_manifest or []
        listed = 0
        for m in manifest:
            if m.get("kind") in ("document", "note"):
                type_label = "Dokument" if m["kind"] == "document" else "Anteckning"
                lines.append(f"- [{type_label}] {m.get('id')} (sanitize: {m.get('sanitize_level')})")
                listed += 1
                if listed >= 10:
                    break
        remaining = sum(1 for m in manifest if m.get("kind") in ("document", "note")) - listed
        if remaining > 0:
            lines.append(f"(+{remaining} fler)")
        lines.append("")
        lines.append("## 5. Risker och integritet")
        lines.append("")
        lines.append("Inga tecken på PII i output och re-ID guard passerade utan varningar.")
        lines.append("")
        lines.append("## 6. Rekommenderade nästa steg")
        lines.append("")
        next_steps = llm_json.get("next_steps") or []
        if next_steps:
            for step in next_steps[:7]:
                lines.append(f"- {step}")
        else:
            lines.append("- Inga explicita nästa steg identifierade.")
        lines.append("")
        lines.append("## Bilaga: Audit")
        lines.append("")
        lines.append(f"Policy: {policy.policy_id} v{policy.policy_version}")
        lines.append(f"Ruleset: {policy.ruleset_hash}")
        lines.append(f"Ingångsfingerprint: {pack.input_fingerprint[:16]}...")
        lines.append("")
        final_rendered_markdown = "\n".join(lines)

        # Final output gate (för att undvika quote-loop och säkerställa fail-closed)
        final_candidate = final_rendered_markdown
        is_safe, pii_reasons = pii_gate_check(final_candidate)
        output_gate_reasons = []
        if not is_safe:
            output_gate_reasons.extend([f"pii_gate_{reason}" for reason in pii_reasons])
        re_id_pass, re_id_reasons = re_id_guard(final_candidate, input_texts, policy)
        if not re_id_pass:
            output_gate_reasons.extend(re_id_reasons)
        if output_gate_reasons:
            raise HTTPException(
                status_code=400,
                detail=KnoxErrorResponse(
                    error_code="OUTPUT_GATE_FAILED",
                    reasons=output_gate_reasons,
                    detail="Output gate validation failed"
                ).model_dump()
            )

        final_rendered_markdown = final_candidate

        latency_ms = int((time.time() - start_time) * 1000)
        gate_results = {"input": {"pass": True, "reasons": []}, "output": {"pass": True, "reasons": []}}

        db_report = KnoxReport(
            project_id=request.project_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            ruleset_hash=policy.ruleset_hash,
            template_id=request.template_id,
            engine_id=engine_id_current,
            input_fingerprint=pack.input_fingerprint,
            input_manifest=pack.input_manifest,
            gate_results=gate_results,
            rendered_markdown=final_rendered_markdown,
            latency_ms=latency_ms if latency_ms else llm_latency_ms
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        return KnoxReportResponse(
            id=db_report.id,
            project_id=db_report.project_id,
            policy_id=db_report.policy_id,
            policy_version=db_report.policy_version,
            ruleset_hash=db_report.ruleset_hash,
            template_id=db_report.template_id,
            engine_id=db_report.engine_id,
            input_fingerprint=db_report.input_fingerprint,
            input_manifest=db_report.input_manifest,
            gate_results=db_report.gate_results,
            rendered_markdown=db_report.rendered_markdown,
            created_at=db_report.created_at,
            latency_ms=db_report.latency_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Fort Knox compile(langchain): Unexpected error: {e}",
            extra={
                "project_id": request.project_id,
                "policy_id": request.policy_id,
                "template_id": request.template_id
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=KnoxErrorResponse(
                error_code="INTERNAL_ERROR",
                reasons=["unexpected_error"],
                detail=type(e).__name__
            ).model_dump()
        )


class KnoxReportToDocumentRequest(BaseModel):
    report_id: int


@app.post("/api/fortknox/compile/jobs", response_model=AiJobResponse, status_code=202)
async def compile_fortknox_report_job(
    request: KnoxCompileRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    username: str = Depends(verify_basic_auth),
    __rl: bool = Depends(rate_limit("fortknox_compile", 6)),
):
    """
    Skapa ett bakgrundsjobb för Fort Knox-rapport.
    Demo-safe: om ASYNC_JOBS inte är aktivt -> 409 så klient kan falla tillbaka till sync-endpoint.
    """
    if not ASYNC_JOBS_ENABLED:
        raise HTTPException(status_code=409, detail="Async jobs disabled")

    job = AiJob(
        kind="fortknox_compile",
        status=AiJobStatus.QUEUED,
        progress=0,
        project_id=request.project_id,
        actor=username,
        payload=_safe_event_metadata({
            "project_id": request.project_id,
            "policy_id": request.policy_id,
            "template_id": request.template_id,
            "snapshot_mode": bool(request.snapshot_mode),
            "selection": {
                "include": len(request.selection.include) if request.selection and request.selection.include else 0,
                "exclude": len(request.selection.exclude) if request.selection and request.selection.exclude else 0
            }
        }, context="audit")
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Kör samma pipeline via intern HTTP för att undvika duplicering
    background_tasks.add_task(
        _run_job_http_post,
        job.id,
        "http://127.0.0.1:8000/api/fortknox/compile",
        json_body=request.model_dump(),
        auth_user=BASIC_AUTH_ADMIN_USER,
        auth_pass=BASIC_AUTH_ADMIN_PASS
    )
    return _job_to_response(job)


@app.post("/api/fortknox/compile/langchain/jobs", response_model=AiJobResponse, status_code=202)
async def compile_fortknox_report_langchain_job(
    request: KnoxCompileRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    username: str = Depends(verify_basic_auth),
    __rl: bool = Depends(rate_limit("fortknox_compile", 6)),
):
    """
    Skapa ett bakgrundsjobb för LangChain-varianten av Fort Knox.
    Demo-safe: om ASYNC_JOBS inte är aktivt -> 409 så klient kan falla tillbaka.
    """
    if not ASYNC_JOBS_ENABLED:
        raise HTTPException(status_code=409, detail="Async jobs disabled")

    job = AiJob(
        kind="fortknox_compile_langchain",
        status=AiJobStatus.QUEUED,
        progress=0,
        project_id=request.project_id,
        actor=username,
        payload=_safe_event_metadata({
            "project_id": request.project_id,
            "policy_id": request.policy_id,
            "template_id": request.template_id,
            "snapshot_mode": bool(request.snapshot_mode),
            "selection": {
                "include": len(request.selection.include) if request.selection and request.selection.include else 0,
                "exclude": len(request.selection.exclude) if request.selection and request.selection.exclude else 0
            }
        }, context="audit")
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _run_job_http_post,
        job.id,
        "http://127.0.0.1:8000/api/fortknox/compile/langchain",
        json_body=request.model_dump(),
        auth_user=BASIC_AUTH_ADMIN_USER,
        auth_pass=BASIC_AUTH_ADMIN_PASS
    )
    return _job_to_response(job)


@app.post("/api/projects/{project_id}/documents/from-knox-report", response_model=DocumentListResponse, status_code=201)
async def create_document_from_knox_report(
    project_id: int,
    body: KnoxReportToDocumentRequest,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Spara en Fort Knox-rapport som ett dokument i projektet.
    - Filnamn baseras på rapportens H1-title (slug + datum) för showreel.
    - Dokumentet markeras i document_metadata som fortknox_report och exkluderas från future snapshot-underlag.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    report = db.query(KnoxReport).filter(KnoxReport.id == body.report_id, KnoxReport.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="KnoxReport not found")
    if not (report.rendered_markdown or "").strip():
        raise HTTPException(status_code=409, detail="KnoxReport has no rendered_markdown")

    # Idempotens: om rapporten redan sparats som dokument i projektet, returnera befintligt.
    # (Undviker dubletter vid upprepade klick eller reload.)
    existing_docs = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at.desc(), Document.id.desc()).all()
    for d in existing_docs:
        meta = getattr(d, "document_metadata", None) or {}
        if meta.get("source_type") == "fortknox_report" and meta.get("knox_report_id") == report.id:
            return DocumentListResponse(
                id=d.id,
                project_id=d.project_id,
                filename=d.filename,
                file_type=d.file_type,
                classification=d.classification.value,
                sanitize_level=d.sanitize_level.value,
                usage_restrictions=d.usage_restrictions,
                pii_gate_reasons=d.pii_gate_reasons,
                created_at=d.created_at
            )

    import re
    import uuid
    from datetime import datetime

    # Extrahera title från första H1-raden: "# Title"
    md = report.rendered_markdown.strip()
    title = ""
    for line in md.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if not title:
        title = f"FortKnox rapport {report.id}"

    # Slugga title för filsystem
    # Behåll bokstäver, siffror, mellanslag, bindestreck och svenska tecken.
    safe_title = re.sub(r"[^\w\s\-åäöÅÄÖ]", "", title)
    safe_title = re.sub(r"\s+", "-", safe_title.strip().lower())
    safe_title = safe_title[:80] if safe_title else f"fortknox-rapport-{report.id}"

    date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"fortknox-{report.policy_id}-{date_prefix}-{safe_title}.md"
    filename = filename[:140]  # extra safety

    # Skriv fil till uploads (server-side). Inget innehåll i loggar.
    file_id = str(uuid.uuid4())
    permanent_path = UPLOAD_DIR / f"{file_id}.md"
    with open(permanent_path, "w", encoding="utf-8") as f:
        f.write(md + "\n")

    db_document = Document(
        project_id=project_id,
        filename=filename,
        file_type="txt",
        classification=project.classification,
        masked_text=md,
        file_path=str(permanent_path),
        sanitize_level=SanitizeLevel.STRICT,
        usage_restrictions={"ai_allowed": True, "export_allowed": True, "fortknox_excluded": True},
        pii_gate_reasons=None,
        document_metadata={
            "source_type": "fortknox_report",
            "knox_report_id": report.id,
            "policy_id": report.policy_id,
            "policy_version": report.policy_version,
            "template_id": report.template_id,
            "input_fingerprint": report.input_fingerprint
        }
    )
    db.add(db_document)

    event = ProjectEvent(
        project_id=project_id,
        event_type="fortknox_report_saved_as_document",
        actor=username,
        event_metadata=_safe_event_metadata({
            "report_id": report.id,
            "document_id": None,  # filled after commit
            "policy_id": report.policy_id,
            "template_id": report.template_id
        }, context="audit")
    )
    db.add(event)

    db.commit()
    db.refresh(db_document)
    event.event_metadata["document_id"] = db_document.id
    db.commit()

    return DocumentListResponse(
        id=db_document.id,
        project_id=db_document.project_id,
        filename=db_document.filename,
        file_type=db_document.file_type,
        classification=db_document.classification.value,
        sanitize_level=db_document.sanitize_level.value,
        usage_restrictions=db_document.usage_restrictions,
        pii_gate_reasons=db_document.pii_gate_reasons,
        created_at=db_document.created_at
    )


@app.post("/api/projects/{project_id}/recordings/jobs", response_model=AiJobResponse, status_code=202)
async def upload_recording_job(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
    username: str = Depends(verify_basic_auth),
    __rl: bool = Depends(rate_limit("upload", 20)),
):
    """
    Skapa ett bakgrundsjobb för röstmemo/transkription.
    Demo-safe: om ASYNC_JOBS inte är aktivt -> 409 så klient kan falla tillbaka till sync-endpoint.
    """
    if not ASYNC_JOBS_ENABLED:
        raise HTTPException(status_code=409, detail="Async jobs disabled")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_content = await file.read()
    file_size = len(file_content)
    if file_size > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 25MB")

    # Spara till temporär fil (för att kunna skicka multipart internt)
    temp_id = str(uuid.uuid4())
    audio_ext = os.path.splitext(file.filename or "")[1] or ".mp3"
    temp_path = UPLOAD_DIR / f"job_audio_{temp_id}{audio_ext}"
    with open(temp_path, "wb") as f:
        f.write(file_content)

    # Skapa jobbrad (metadata-only)
    job = AiJob(
        kind="recording_transcribe",
        status=AiJobStatus.QUEUED,
        progress=0,
        project_id=project_id,
        actor=username,
        payload=_safe_event_metadata({
            "project_id": project_id,
            "mime": file.content_type or "application/octet-stream",
            "size_bytes": file_size
        }, context="audit")
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    def _run_recording_job():
        import requests
        try:
            _update_job(job.id, status=AiJobStatus.RUNNING, progress=10)
            with open(temp_path, "rb") as fh:
                files = {"file": (file.filename or f"recording{audio_ext}", fh, file.content_type or "application/octet-stream")}
                r = requests.post(
                    f"http://127.0.0.1:8000/api/projects/{project_id}/recordings",
                    files=files,
                    auth=(BASIC_AUTH_ADMIN_USER, BASIC_AUTH_ADMIN_PASS),
                    timeout=180
                )
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            if 200 <= r.status_code < 300:
                data = None
                try:
                    data = r.json()
                except Exception:
                    data = None
                _update_job(
                    job.id,
                    status=AiJobStatus.SUCCEEDED,
                    progress=100,
                    result={"http_status": r.status_code, "data": _safe_job_result(data)}
                )
                return
            _update_job(job.id, status=AiJobStatus.FAILED, progress=100, error_code=f"HTTP_{r.status_code}", error_detail="Recording job failed")
        except Exception as e:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            _update_job(job.id, status=AiJobStatus.FAILED, progress=100, error_code="JOB_EXCEPTION", error_detail=type(e).__name__)

    background_tasks.add_task(_run_recording_job)
    return _job_to_response(job)


class SanitizeLevelUpdate(BaseModel):
    level: str  # "strict" | "paranoid"


@app.put("/api/documents/{document_id}/sanitize-level")
async def update_document_sanitize_level(
    document_id: int,
    body: SanitizeLevelUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Bumpa dokumentets sanitize_level deterministiskt och re-sanitera masked_text.
    Idempotent: samma nivå igen gör ingen ändring.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    desired = (body.level or "").lower()
    if desired not in ("strict", "paranoid"):
        raise HTTPException(status_code=422, detail=[{"loc": ["body","level"], "msg": "level must be 'strict' or 'paranoid'"}])
    # Order mapping
    order = {"normal": 0, "strict": 1, "paranoid": 2}
    current = getattr(doc.sanitize_level, "value", str(doc.sanitize_level))
    if order[current] >= order[desired]:
        # No downgrade or same level: return current state
        return {
            "id": doc.id,
            "sanitize_level": current,
            "masked_text": doc.masked_text
        }
    # Re-mask current masked_text with higher level (safe, deterministic)
    try:
        # Fail-closed ONLY om vi saknar både originalfil OCH maskat innehåll.
        # Scout-importerade dokument har ofta placeholder file_path (ingen faktisk fil),
        # men masked_text i DB räcker för deterministisk bump.
        import os
        file_path = str(doc.file_path or "")
        file_exists = bool(file_path) and os.path.exists(file_path)
        has_masked = bool((doc.masked_text or "").strip())
        is_scout_placeholder = file_path.startswith("scout_import_")
        if (not file_exists) and (not has_masked) and (not is_scout_placeholder):
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "ORIGINAL_MISSING",
                    "item": {"type": "document", "id": document_id},
                    "message": "Original file not found and no masked_text available. Cannot re-sanitize."
                }
            )
        # Normalize first
        norm = normalize_text(doc.masked_text or "")
        if desired == "paranoid":
            new_masked = mask_text(norm, level="paranoid")
            # Maska datum/tid för paranoid
            new_masked, datetime_stats = mask_datetime(new_masked, level="paranoid")
        else:
            new_masked = mask_text(norm, level="strict")
            # Maska datum/tid för strict
            new_masked, datetime_stats = mask_datetime(new_masked, level="strict")
        is_safe, reasons = pii_gate_check(new_masked)
        if not is_safe:
            raise HTTPException(status_code=400, detail=KnoxErrorResponse(
                error_code="INPUT_GATE_FAILED",
                reasons=[f"pii_gate_{r}" for r in reasons],
                detail="PII gate failed after sanitize bump"
            ).model_dump())
        # Persist changes
        doc.masked_text = new_masked
        doc.sanitize_level = SanitizeLevel.STRICT if desired == "strict" else SanitizeLevel.PARANOID
        db.add(doc)
        db.commit()
        return {
            "id": doc.id,
            "sanitize_level": getattr(doc.sanitize_level, "value", str(doc.sanitize_level)),
            "masked_text": doc.masked_text,
            "datetime_masked": datetime_stats["datetime_masked"],
            "datetime_mask_count": datetime_stats["datetime_mask_count"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bump document sanitize level: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update document sanitize level")


@app.put("/api/projects/{project_id}/notes/{note_id}/sanitize-level")
async def update_note_sanitize_level(
    project_id: int,
    note_id: int,
    body: SanitizeLevelUpdate,
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Bumpa anteckningens sanitize_level deterministiskt och re-sanitera masked_body.
    Idempotent: samma nivå igen gör ingen ändring.
    """
    note = db.query(ProjectNote).filter(ProjectNote.id == note_id, ProjectNote.project_id == project_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    desired = (body.level or "").lower()
    if desired not in ("strict", "paranoid"):
        raise HTTPException(status_code=422, detail=[{"loc": ["body","level"], "msg": "level must be 'strict' or 'paranoid'"}])
    order = {"normal": 0, "strict": 1, "paranoid": 2}
    current = getattr(note.sanitize_level, "value", str(note.sanitize_level))
    if order[current] >= order[desired]:
        return {
            "id": note.id,
            "sanitize_level": current,
            "masked_body": note.masked_body
        }
    try:
        norm = normalize_text(note.masked_body or "")
        if desired == "paranoid":
            new_masked = mask_text(norm, level="paranoid")
            # Maska datum/tid för paranoid
            new_masked, datetime_stats = mask_datetime(new_masked, level="paranoid")
        else:
            new_masked = mask_text(norm, level="strict")
            # Maska datum/tid för strict
            new_masked, datetime_stats = mask_datetime(new_masked, level="strict")
        is_safe, reasons = pii_gate_check(new_masked)
        if not is_safe:
            raise HTTPException(status_code=400, detail=KnoxErrorResponse(
                error_code="INPUT_GATE_FAILED",
                reasons=[f"pii_gate_{r}" for r in reasons],
                detail="PII gate failed after sanitize bump"
            ).model_dump())
        note.masked_body = new_masked
        note.sanitize_level = SanitizeLevel.STRICT if desired == "strict" else SanitizeLevel.PARANOID
        db.add(note)
        db.commit()
        return {
            "id": note.id,
            "sanitize_level": getattr(note.sanitize_level, "value", str(note.sanitize_level)),
            "masked_body": note.masked_body,
            "datetime_masked": datetime_stats["datetime_masked"],
            "datetime_mask_count": datetime_stats["datetime_mask_count"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bump note sanitize level: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update note sanitize level")