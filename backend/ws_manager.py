import asyncio

# job_id -> asyncio.Queue of status update dicts
_queues: dict[str, asyncio.Queue] = {}


def register(job_id: str) -> asyncio.Queue:
    """Create a queue for a job and return it. Called when a WebSocket connects."""
    q: asyncio.Queue = asyncio.Queue()
    _queues[job_id] = q
    return q


def unregister(job_id: str) -> None:
    """Remove a job's queue. Called when the WebSocket disconnects."""
    _queues.pop(job_id, None)


async def push(job_id: str, data: dict) -> None:
    """Push an update to the job's queue if a WebSocket is listening."""
    q = _queues.get(job_id)
    if q is not None:
        await q.put(data)
