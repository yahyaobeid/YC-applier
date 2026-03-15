"""Tests for api/routes/dashboard.py."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from api.state import pipeline_state

client = TestClient(app)

_MOCK_SETTINGS = {
    "paths": {"resume": "resume/resume.pdf", "applied_log": "data/applied_jobs.json"},
    "filters": {"roles": ["Backend"], "remote_only": True},
    "matching": {"min_match_score": 70, "max_jobs_per_run": 30},
    "behavior": {
        "review_mode": True,
        "auto_apply_above_score": 90,
        "application_delay_seconds": 30,
    },
}


def _make_app(job_id: str, date: str, status: str = "submitted") -> dict:
    return {
        "job_id": job_id,
        "job_title": f"Engineer {job_id}",
        "company_name": f"Company {job_id}",
        "job_url": "https://example.com",
        "match_score": 80,
        "status": status,
        "submitted_at": date,
    }


@pytest.fixture(autouse=True)
def reset_state():
    pipeline_state.reset()
    yield
    pipeline_state.reset()


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------

def test_stats_no_applications():
    with patch("api.routes.dashboard._load_applications", return_value=[]):
        r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_applications"] == 0
    assert data["submitted"] == 0
    assert data["pending_review"] == 0
    assert data["this_week"] == 0


def test_stats_total_applications():
    apps = [_make_app(f"j{i}", "2026-03-10T10:00:00+00:00") for i in range(7)]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/stats")
    assert r.json()["total_applications"] == 7


def test_stats_submitted_count():
    apps = [
        _make_app("j1", "2026-03-10T10:00:00+00:00", "submitted"),
        _make_app("j2", "2026-03-10T10:00:00+00:00", "submitted"),
        _make_app("j3", "2026-03-10T10:00:00+00:00", "auto_approved"),
    ]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/stats")
    assert r.json()["submitted"] == 2


def test_stats_pending_review_from_pipeline_state():
    pipeline_state.drafts = [
        {"id": "j1", "status": "pending"},
        {"id": "j2", "status": "pending"},
        {"id": "j3", "status": "approved"},
    ]
    with patch("api.routes.dashboard._load_applications", return_value=[]):
        r = client.get("/api/stats")
    assert r.json()["pending_review"] == 2


def test_stats_this_week_count():
    # Use dates near today (2026-03-15)
    apps = [
        _make_app("j1", "2026-03-14T10:00:00+00:00"),  # yesterday — in week
        _make_app("j2", "2026-03-13T10:00:00+00:00"),  # 2 days ago — in week
        _make_app("j3", "2026-03-01T10:00:00+00:00"),  # 2 weeks ago — out
    ]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/stats")
    # j1 and j2 are within 7 days
    assert r.json()["this_week"] >= 2


def test_stats_status_breakdown():
    apps = [
        _make_app("j1", "2026-03-10T10:00:00+00:00", "submitted"),
        _make_app("j2", "2026-03-10T10:00:00+00:00", "auto_approved"),
        _make_app("j3", "2026-03-10T10:00:00+00:00", "submitted"),
    ]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/stats")
    breakdown = r.json()["status_breakdown"]
    assert breakdown["submitted"] == 2
    assert breakdown["auto_approved"] == 1


# ---------------------------------------------------------------------------
# GET /api/applications/recent
# ---------------------------------------------------------------------------

def test_recent_empty():
    with patch("api.routes.dashboard._load_applications", return_value=[]):
        r = client.get("/api/applications/recent")
    assert r.status_code == 200
    assert r.json() == []


def test_recent_default_limit_10():
    apps = [_make_app(f"j{i}", f"2026-03-{i+1:02d}T10:00:00+00:00") for i in range(15)]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/applications/recent")
    assert len(r.json()) == 10


def test_recent_custom_limit():
    apps = [_make_app(f"j{i}", f"2026-03-{i+1:02d}T10:00:00+00:00") for i in range(15)]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/applications/recent?limit=5")
    assert len(r.json()) == 5


def test_recent_sorted_newest_first():
    apps = [
        _make_app("j1", "2026-03-10T10:00:00+00:00"),
        _make_app("j2", "2026-03-15T10:00:00+00:00"),
        _make_app("j3", "2026-03-12T10:00:00+00:00"),
    ]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/applications/recent")
    result = r.json()
    dates = [a["submitted_at"] for a in result]
    assert dates == sorted(dates, reverse=True)


def test_recent_fewer_than_limit():
    apps = [_make_app("j1", "2026-03-10T10:00:00+00:00")]
    with patch("api.routes.dashboard._load_applications", return_value=apps):
        r = client.get("/api/applications/recent?limit=10")
    assert len(r.json()) == 1
