"""Tests for api/state.py — PipelineState."""

import asyncio

import pytest

from api.state import PipelineState


def make_state() -> PipelineState:
    return PipelineState()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def test_initial_status():
    s = make_state()
    assert s.status == "idle"
    assert s.progress == []
    assert s.drafts == []
    assert s.error is None


# ---------------------------------------------------------------------------
# push_event
# ---------------------------------------------------------------------------

def test_push_event_appends_to_progress():
    s = make_state()
    s.push_event("progress", "hello")
    assert len(s.progress) == 1
    assert s.progress[0]["type"] == "progress"
    assert s.progress[0]["message"] == "hello"


def test_push_event_includes_timestamp():
    s = make_state()
    s.push_event("progress", "msg")
    assert "timestamp" in s.progress[0]
    assert s.progress[0]["timestamp"].endswith("Z")


def test_push_event_merges_extra_fields():
    s = make_state()
    s.push_event("status_change", "done", {"count": 5, "detail": "ok"})
    assert s.progress[0]["count"] == 5
    assert s.progress[0]["detail"] == "ok"


def test_push_event_multiple():
    s = make_state()
    for i in range(3):
        s.push_event("progress", f"step {i}")
    assert len(s.progress) == 3


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

def test_reset_clears_all_fields():
    s = make_state()
    s.status = "running"
    s.error = "oops"
    s.progress.append({"type": "x", "message": "y", "timestamp": "t"})
    s.drafts.append({"id": "j1", "status": "pending"})
    s.reset()
    assert s.status == "idle"
    assert s.progress == []
    assert s.drafts == []
    assert s.error is None


# ---------------------------------------------------------------------------
# get_draft / update_draft
# ---------------------------------------------------------------------------

def test_get_draft_found():
    s = make_state()
    s.drafts.append({"id": "j1", "job_title": "Engineer", "status": "pending"})
    d = s.get_draft("j1")
    assert d is not None
    assert d["job_title"] == "Engineer"


def test_get_draft_not_found():
    s = make_state()
    assert s.get_draft("nonexistent") is None


def test_get_draft_returns_independent_copy():
    s = make_state()
    s.drafts.append({"id": "j1", "status": "pending"})
    copy = s.get_draft("j1")
    copy["status"] = "approved"
    assert s.drafts[0]["status"] == "pending"  # original unchanged


def test_update_draft_changes_field():
    s = make_state()
    s.drafts.append({"id": "j1", "status": "pending"})
    result = s.update_draft("j1", status="approved")
    assert result is True
    assert s.drafts[0]["status"] == "approved"


def test_update_draft_multiple_kwargs():
    s = make_state()
    s.drafts.append({"id": "j1", "status": "pending", "draft_paragraph": "old"})
    s.update_draft("j1", status="approved", draft_paragraph="new text")
    assert s.drafts[0]["status"] == "approved"
    assert s.drafts[0]["draft_paragraph"] == "new text"


def test_update_draft_not_found_returns_false():
    s = make_state()
    assert s.update_draft("nonexistent", status="approved") is False


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def test_to_dict_structure():
    s = make_state()
    s.status = "awaiting_review"
    s.drafts.append({"id": "j1", "status": "pending"})
    s.error = None
    d = s.to_dict()
    assert d["status"] == "awaiting_review"
    assert len(d["drafts"]) == 1
    assert d["error"] is None
    assert isinstance(d["progress"], list)


def test_to_dict_drafts_are_copies():
    s = make_state()
    s.drafts.append({"id": "j1", "status": "pending"})
    d = s.to_dict()
    d["drafts"][0]["status"] = "approved"
    assert s.drafts[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# SSE queue management
# ---------------------------------------------------------------------------

def test_add_sse_queue():
    s = make_state()
    q = asyncio.Queue()
    s.add_sse_queue(q)
    assert q in s._sse_queues


def test_remove_sse_queue():
    s = make_state()
    q = asyncio.Queue()
    s.add_sse_queue(q)
    s.remove_sse_queue(q)
    assert q not in s._sse_queues


def test_remove_nonexistent_queue_no_error():
    s = make_state()
    q = asyncio.Queue()
    s.remove_sse_queue(q)  # should not raise


def test_multiple_queues():
    s = make_state()
    queues = [asyncio.Queue() for _ in range(3)]
    for q in queues:
        s.add_sse_queue(q)
    assert len(s._sse_queues) == 3
    s.remove_sse_queue(queues[1])
    assert len(s._sse_queues) == 2


@pytest.mark.asyncio
async def test_push_event_notifies_sse_queue():
    s = make_state()
    loop = asyncio.get_running_loop()
    s.set_loop(loop)
    q: asyncio.Queue = asyncio.Queue()
    s.add_sse_queue(q)

    s.push_event("progress", "test message")
    await asyncio.sleep(0)  # let call_soon_threadsafe fire

    assert not q.empty()
    event = q.get_nowait()
    assert event["type"] == "progress"
    assert event["message"] == "test message"


@pytest.mark.asyncio
async def test_push_event_notifies_multiple_queues():
    s = make_state()
    loop = asyncio.get_running_loop()
    s.set_loop(loop)
    queues = [asyncio.Queue() for _ in range(3)]
    for q in queues:
        s.add_sse_queue(q)

    s.push_event("progress", "broadcast")
    await asyncio.sleep(0)

    for q in queues:
        assert not q.empty()
        assert q.get_nowait()["message"] == "broadcast"


@pytest.mark.asyncio
async def test_push_event_no_notification_without_loop():
    s = make_state()  # no set_loop call
    q: asyncio.Queue = asyncio.Queue()
    s.add_sse_queue(q)
    s.push_event("progress", "msg")
    await asyncio.sleep(0)
    assert q.empty()  # no loop set, so no notification — but event still stored
    assert len(s.progress) == 1
