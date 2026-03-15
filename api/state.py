"""Global pipeline state and SSE event management."""

import asyncio
import datetime
import threading
from typing import Optional


class PipelineState:
    def __init__(self):
        self.status: str = "idle"  # idle | running | awaiting_review | submitting | complete | error
        self.progress: list[dict] = []
        self.drafts: list[dict] = []
        self.error: Optional[str] = None
        self._lock = threading.Lock()
        self._sse_queues: list[asyncio.Queue] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def push_event(self, event_type: str, message: str, extra: dict = None) -> None:
        event = {
            "type": event_type,
            "message": message,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            **(extra or {}),
        }
        with self._lock:
            self.progress.append(event)
            queues = list(self._sse_queues)
        if self._loop and queues:
            for q in queues:
                self._loop.call_soon_threadsafe(q.put_nowait, event)

    def add_sse_queue(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._sse_queues.append(q)

    def remove_sse_queue(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self._sse_queues:
                self._sse_queues.remove(q)

    def reset(self) -> None:
        with self._lock:
            self.status = "idle"
            self.progress = []
            self.drafts = []
            self.error = None

    def get_draft(self, draft_id: str) -> Optional[dict]:
        with self._lock:
            for d in self.drafts:
                if d["id"] == draft_id:
                    return dict(d)
        return None

    def update_draft(self, draft_id: str, **kwargs) -> bool:
        with self._lock:
            for d in self.drafts:
                if d["id"] == draft_id:
                    d.update(kwargs)
                    return True
        return False

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "status": self.status,
                "progress": list(self.progress),
                "drafts": [dict(d) for d in self.drafts],
                "error": self.error,
            }


pipeline_state = PipelineState()
