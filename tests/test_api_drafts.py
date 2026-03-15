"""Tests for api/routes/drafts.py."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.state import pipeline_state

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    pipeline_state.reset()
    yield
    pipeline_state.reset()


def _add_draft(draft_id: str = "j1", status: str = "pending") -> dict:
    draft = {
        "id": draft_id,
        "job_id": draft_id,
        "job_title": "Backend Engineer",
        "job_url": f"https://workatastartup.com/jobs/{draft_id}",
        "company_name": "Acme",
        "company_batch": "W24",
        "match_score": 85,
        "match_reasoning": "Strong Python match",
        "draft_paragraph": "I am a great fit for this role.",
        "status": status,
    }
    pipeline_state.drafts.append(draft)
    return draft


# ---------------------------------------------------------------------------
# GET /api/drafts
# ---------------------------------------------------------------------------

def test_list_drafts_empty():
    r = client.get("/api/drafts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_drafts_returns_all():
    _add_draft("j1")
    _add_draft("j2")
    r = client.get("/api/drafts")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_drafts_preserves_fields():
    _add_draft("j1")
    r = client.get("/api/drafts")
    d = r.json()[0]
    assert d["id"] == "j1"
    assert d["job_title"] == "Backend Engineer"
    assert d["match_score"] == 85
    assert d["status"] == "pending"


# ---------------------------------------------------------------------------
# POST /api/drafts/{id}/approve
# ---------------------------------------------------------------------------

def test_approve_draft_success():
    _add_draft("j1")
    r = client.post("/api/drafts/j1/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_approve_draft_updates_state():
    _add_draft("j1")
    client.post("/api/drafts/j1/approve")
    assert pipeline_state.drafts[0]["status"] == "approved"


def test_approve_draft_not_found():
    r = client.post("/api/drafts/nonexistent/approve")
    assert r.status_code == 404


def test_approve_only_target_draft():
    _add_draft("j1")
    _add_draft("j2")
    client.post("/api/drafts/j1/approve")
    assert pipeline_state.drafts[0]["status"] == "approved"
    assert pipeline_state.drafts[1]["status"] == "pending"


# ---------------------------------------------------------------------------
# POST /api/drafts/{id}/edit
# ---------------------------------------------------------------------------

def test_edit_draft_success():
    _add_draft("j1")
    r = client.post("/api/drafts/j1/edit", json={"draft_paragraph": "New text here."})
    assert r.status_code == 200
    assert r.json()["status"] == "edited"


def test_edit_draft_updates_paragraph():
    _add_draft("j1")
    client.post("/api/drafts/j1/edit", json={"draft_paragraph": "Updated paragraph."})
    assert pipeline_state.drafts[0]["draft_paragraph"] == "Updated paragraph."


def test_edit_draft_sets_approved():
    _add_draft("j1", status="pending")
    client.post("/api/drafts/j1/edit", json={"draft_paragraph": "New text."})
    assert pipeline_state.drafts[0]["status"] == "approved"


def test_edit_draft_not_found():
    r = client.post("/api/drafts/nonexistent/edit", json={"draft_paragraph": "text"})
    assert r.status_code == 404


def test_edit_draft_missing_body_returns_422():
    _add_draft("j1")
    r = client.post("/api/drafts/j1/edit", json={})
    assert r.status_code == 422


def test_edit_draft_empty_paragraph_allowed():
    _add_draft("j1")
    r = client.post("/api/drafts/j1/edit", json={"draft_paragraph": ""})
    assert r.status_code == 200
    assert pipeline_state.drafts[0]["draft_paragraph"] == ""


# ---------------------------------------------------------------------------
# POST /api/drafts/{id}/skip
# ---------------------------------------------------------------------------

def test_skip_draft_success():
    _add_draft("j1")
    r = client.post("/api/drafts/j1/skip")
    assert r.status_code == 200
    assert r.json()["status"] == "skipped"


def test_skip_draft_updates_state():
    _add_draft("j1")
    client.post("/api/drafts/j1/skip")
    assert pipeline_state.drafts[0]["status"] == "skipped"


def test_skip_draft_not_found():
    r = client.post("/api/drafts/nonexistent/skip")
    assert r.status_code == 404


def test_skip_only_target_draft():
    _add_draft("j1")
    _add_draft("j2")
    client.post("/api/drafts/j2/skip")
    assert pipeline_state.drafts[0]["status"] == "pending"
    assert pipeline_state.drafts[1]["status"] == "skipped"
