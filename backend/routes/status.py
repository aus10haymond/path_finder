import json

from fastapi import APIRouter, HTTPException

from database import get_job
from models import JobStatusResponse

router = APIRouter()


@router.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        id=job["id"],
        status=job["status"],
        progress=job.get("progress"),
        result=json.loads(job["result_json"]) if job.get("result_json") else None,
        error=job.get("error"),
    )
