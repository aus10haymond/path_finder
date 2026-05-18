import json

from fastapi import APIRouter

from database import list_jobs

router = APIRouter()


@router.get("/api/jobs")
async def get_jobs():
    jobs = await list_jobs()
    return [
        {
            "id": j["id"],
            "status": j["status"],
            "progress": j.get("progress"),
            "result": json.loads(j["result_json"]) if j.get("result_json") else None,
            "error": j.get("error"),
            "created_at": j["created_at"],
        }
        for j in jobs
    ]
