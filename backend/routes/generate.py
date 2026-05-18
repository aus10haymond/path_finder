from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from config import settings
from database import create_job
from models import GenerateRequest
from worker import run_job

router = APIRouter()

# ip -> last job creation time (UTC)
_last_job_time: dict[str, datetime] = {}
RATE_LIMIT_SECONDS = 300


@router.post("/api/generate")
async def generate(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    token: str = Query(default=""),
):
    if settings.secret_url_token and token != settings.secret_url_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not request.cities:
        raise HTTPException(status_code=422, detail="At least one city is required")

    ip = http_request.client.host if http_request.client else "unknown"
    now = datetime.now(timezone.utc)
    last = _last_job_time.get(ip)
    if last and (now - last).total_seconds() < RATE_LIMIT_SECONDS:
        raise HTTPException(status_code=429, detail="A job is already running. Please wait before generating again.")
    _last_job_time[ip] = now

    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    await create_job(job_id, created_at)
    background_tasks.add_task(run_job, job_id, request)
    return {"job_id": job_id}
