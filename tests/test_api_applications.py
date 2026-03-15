"""Tests for api/routes/applications.py."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app

client = TestClient(app)


def _make_app(job_id: str, date: str, status: str = "submitted") -> dict:
    return {
        "job_id": job_id,
        "job_title": f"Role {job_id}",
        "company_name": f"Company {job_id}",
        "job_url": f"https://workatastartup.com/jobs/{job_id}",
        "match_score": 80,
        "status": status,
        "submitted_at": date,
    }


def _sample_apps() -> list[dict]:
    return [
        _make_app("j1", "2026-03-15T10:00:00+00:00", "submitted"),
        _make_app("j2", "2026-03-14T10:00:00+00:00", "auto_approved"),
        _make_app("j3", "2026-03-13T10:00:00+00:00", "submitted"),
        _make_app("j4", "2026-03-12T10:00:00+00:00", "skipped"),
    ]


# ---------------------------------------------------------------------------
# GET /api/applications
# ---------------------------------------------------------------------------

def test_list_applications_empty():
    with patch("api.routes.applications._load_applications", return_value=[]):
        r = client.get("/api/applications")
    assert r.status_code == 200
    assert r.json() == []


def test_list_applications_returns_all():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications")
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_list_applications_sorted_newest_first():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications")
    dates = [a["submitted_at"] for a in r.json()]
    assert dates == sorted(dates, reverse=True)


def test_filter_by_status_submitted():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications?status=submitted")
    result = r.json()
    assert len(result) == 2
    assert all(a["status"] == "submitted" for a in result)


def test_filter_by_status_auto_approved():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications?status=auto_approved")
    result = r.json()
    assert len(result) == 1
    assert result[0]["job_id"] == "j2"


def test_filter_by_unknown_status_returns_empty():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications?status=nonexistent")
    assert r.json() == []


def test_no_filter_returns_all_statuses():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications")
    statuses = {a["status"] for a in r.json()}
    assert statuses == {"submitted", "auto_approved", "skipped"}


def test_applications_have_expected_fields():
    with patch("api.routes.applications._load_applications", return_value=_sample_apps()):
        r = client.get("/api/applications")
    app_record = r.json()[0]
    for field in ("job_id", "job_title", "company_name", "match_score", "status", "submitted_at"):
        assert field in app_record
