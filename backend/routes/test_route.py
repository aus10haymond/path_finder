from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from config import settings
from database import create_job
from models import GenerateRequest
from worker import run_job

router = APIRouter()


@router.post("/api/test")
async def test_run(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    token: str = Query(default=""),
):
    """Run the full pipeline against the test sheet and test email recipient."""
    if settings.secret_url_token and token != settings.secret_url_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not request.cities:
        raise HTTPException(status_code=422, detail="At least one city is required")

    job_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    await create_job(job_id, created_at)
    background_tasks.add_task(run_job, job_id, request, True)
    return {"job_id": job_id, "test_mode": True}
