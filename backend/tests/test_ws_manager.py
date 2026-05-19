import asyncio

import pytest

import ws_manager


@pytest.fixture(autouse=True)
def clean_queues():
    """Ensure no queues leak between tests."""
    ws_manager._queues.clear()
    yield
    ws_manager._queues.clear()


class TestWsManager:
    def test_register_creates_queue(self):
        q = ws_manager.register("job-1")
        assert isinstance(q, asyncio.Queue)
        assert "job-1" in ws_manager._queues

    def test_unregister_removes_queue(self):
        ws_manager.register("job-2")
        ws_manager.unregister("job-2")
        assert "job-2" not in ws_manager._queues

    def test_unregister_nonexistent_is_safe(self):
        ws_manager.unregister("no-such-job")  # should not raise

    async def test_push_puts_item_in_queue(self):
        q = ws_manager.register("job-3")
        await ws_manager.push("job-3", {"status": "running", "progress": "Fetching..."})
        assert not q.empty()
        item = await q.get()
        assert item["status"] == "running"
        assert item["progress"] == "Fetching..."

    async def test_push_to_unregistered_job_is_silent(self):
        # No queue registered — push should not raise
        await ws_manager.push("phantom-job", {"status": "running"})

    async def test_multiple_pushes_are_queued_in_order(self):
        q = ws_manager.register("job-4")
        updates = [
            {"status": "running", "progress": "Step 1"},
            {"status": "running", "progress": "Step 2"},
            {"status": "complete", "progress": "Done!"},
        ]
        for u in updates:
            await ws_manager.push("job-4", u)

        received = []
        while not q.empty():
            received.append(await q.get())

        assert [r["progress"] for r in received] == ["Step 1", "Step 2", "Done!"]
