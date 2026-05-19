import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from database import get_job
from ws_manager import push, register, unregister

router = APIRouter()
logger = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 25  # send ping before most proxy idle timeouts (30 s)


@router.websocket("/api/ws/{job_id}")
async def websocket_status(websocket: WebSocket, job_id: str):
    await websocket.accept()

    job = await get_job(job_id)
    if not job:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close(code=1008)
        return

    # Always send the current DB state first so the client is never blank,
    # even if some progress events were emitted before the socket connected.
    result = json.loads(job["result_json"]) if job.get("result_json") else None
    await websocket.send_json({
        "status": job["status"],
        "progress": job.get("progress"),
        "result": result,
        "error": job.get("error"),
    })

    if job["status"] in ("complete", "failed"):
        await websocket.close()
        return

    # Job still running — subscribe to live pushes from the worker
    queue = register(job_id)
    try:
        while True:
            try:
                update = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"ping": True})
                except Exception:
                    break
                continue

            await websocket.send_json(update)
            if update.get("status") in ("complete", "failed"):
                break
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for job %s", job_id)
    finally:
        unregister(job_id)
        try:
            await websocket.close()
        except Exception:
            pass
