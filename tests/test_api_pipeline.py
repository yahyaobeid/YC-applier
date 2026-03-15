"""Tests for api/routes/pipeline.py (status, start validation, submit validation)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from api.state import pipeline_state

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    pipeline_state.reset()
    yield
    pipeline_state.reset()


# ---------------------------------------------------------------------------
# GET /api/pipeline/status
# ---------------------------------------------------------------------------

def test_status_idle_on_startup():
    r = client.get("/api/pipeline/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "idle"
    assert data["drafts"] == []
    assert data["progress"] == []
    assert data["error"] is None


def test_status_reflects_state():
    pipeline_state.status = "awaiting_review"
    pipeline_state.drafts = [{"id": "j1", "status": "pending"}]
    r = client.get("/api/pipeline/status")
    data = r.json()
    assert data["status"] == "awaiting_review"
    assert len(data["drafts"]) == 1


def test_status_reflects_error():
    pipeline_state.status = "error"
    pipeline_state.error = "Something went wrong"
    r = client.get("/api/pipeline/status")
    data = r.json()
    assert data["status"] == "error"
    assert data["error"] == "Something went wrong"


def test_status_includes_progress_log():
    pipeline_state.push_event("progress", "step 1")
    pipeline_state.push_event("progress", "step 2")
    r = client.get("/api/pipeline/status")
    assert len(r.json()["progress"]) == 2


# ---------------------------------------------------------------------------
# POST /api/pipeline/start — validation
# ---------------------------------------------------------------------------

def test_start_rejected_while_running():
    pipeline_state.status = "running"
    r = client.post("/api/pipeline/start", json={"dry_run": True, "ai_provider": "anthropic"})
    assert r.status_code == 400


def test_start_rejected_while_submitting():
    pipeline_state.status = "submitting"
    r = client.post("/api/pipeline/start", json={"dry_run": True})
    assert r.status_code == 400


def test_start_allowed_when_idle():
    with patch("api.routes.pipeline._run_pipeline_sync", return_value=[]):
        r = client.post("/api/pipeline/start", json={"dry_run": True, "ai_provider": "anthropic"})
    assert r.status_code == 200
    assert r.json()["status"] == "started"


def test_start_allowed_after_complete():
    pipeline_state.status = "complete"
    with patch("api.routes.pipeline._run_pipeline_sync", return_value=[]):
        r = client.post("/api/pipeline/start", json={"dry_run": True})
    assert r.status_code == 200


def test_start_allowed_after_error():
    pipeline_state.status = "error"
    with patch("api.routes.pipeline._run_pipeline_sync", return_value=[]):
        r = client.post("/api/pipeline/start", json={"dry_run": True})
    assert r.status_code == 200


def test_start_resets_previous_state():
    pipeline_state.status = "error"
    pipeline_state.error = "old error"
    pipeline_state.drafts = [{"id": "j1"}]
    with patch("api.routes.pipeline._run_pipeline_sync", return_value=[]):
        client.post("/api/pipeline/start", json={"dry_run": True})
    # State should have been reset before the background task starts
    assert pipeline_state.error is None
    assert pipeline_state.drafts == []


def test_start_invalid_ai_provider_still_accepted():
    # Provider value is not validated at the route level — passes through to thread
    with patch("api.routes.pipeline._run_pipeline_sync", return_value=[]):
        r = client.post("/api/pipeline/start", json={"dry_run": False, "ai_provider": "unknown"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/pipeline/submit — validation
# ---------------------------------------------------------------------------

def test_submit_rejected_when_idle():
    r = client.post("/api/pipeline/submit", json={"dry_run": True})
    assert r.status_code == 400


def test_submit_rejected_when_running():
    pipeline_state.status = "running"
    r = client.post("/api/pipeline/submit", json={"dry_run": True})
    assert r.status_code == 400


def test_submit_rejected_with_no_approved_drafts():
    pipeline_state.status = "awaiting_review"
    pipeline_state.drafts = [
        {"id": "j1", "status": "pending"},
        {"id": "j2", "status": "skipped"},
    ]
    r = client.post("/api/pipeline/submit", json={"dry_run": True})
    assert r.status_code == 400


def test_submit_accepted_with_approved_drafts():
    pipeline_state.status = "awaiting_review"
    pipeline_state.drafts = [
        {"id": "j1", "status": "approved", "job_title": "Eng", "company_name": "Co",
         "job_url": "https://example.com", "job_id": "j1", "match_score": 85,
         "match_reasoning": "ok", "draft_paragraph": "text"},
    ]
    with patch("api.routes.pipeline._run_submit_sync"):
        r = client.post("/api/pipeline/submit", json={"dry_run": True})
    assert r.status_code == 200
    assert r.json()["status"] == "submitting"
