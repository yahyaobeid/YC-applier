"""Tests for storage/tracker.py."""

import json
from datetime import datetime, timezone

import pytest

from yc_applier.scraper.models import ApplicationDraft, Company, Job
from yc_applier.storage.tracker import ApplicationTracker


def _make_draft(
    job_id: str = "j1",
    title: str = "Backend Engineer",
    company: str = "Acme",
    status: str = "submitted",
) -> ApplicationDraft:
    co = Company(id=company, name=company, batch="W24", description="Cool startup", industry="SaaS")
    job = Job(
        id=job_id,
        url=f"https://workatastartup.com/jobs/{job_id}",
        title=title,
        company=co,
        role_type="backend",
        description="Build scalable APIs",
        requirements="Python",
        location="Remote",
        remote=True,
        scraped_at=datetime.now(timezone.utc),
    )
    return ApplicationDraft(
        job=job,
        match_score=85,
        match_reasoning="Good match",
        draft_paragraph="I am a great fit.",
        status=status,
        submitted_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

def test_empty_tracker_returns_no_records(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    assert tracker.all_records() == []


def test_already_applied_false_when_empty(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    assert tracker.already_applied("j1") is False


# ---------------------------------------------------------------------------
# Record & lookup
# ---------------------------------------------------------------------------

def test_record_marks_as_applied(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    tracker.record_application(_make_draft("j1"))
    assert tracker.already_applied("j1") is True


def test_unrecorded_job_not_applied(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    tracker.record_application(_make_draft("j1"))
    assert tracker.already_applied("j2") is False


def test_all_records_has_correct_fields(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    tracker.record_application(_make_draft("j1", "Backend Engineer", "TechCo"))
    records = tracker.all_records()
    assert len(records) == 1
    rec = records[0]
    assert rec["job_id"] == "j1"
    assert rec["job_title"] == "Backend Engineer"
    assert rec["company_name"] == "TechCo"
    assert rec["match_score"] == 85
    assert rec["status"] == "submitted"
    assert "submitted_at" in rec


def test_multiple_records(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    for i in range(5):
        tracker.record_application(_make_draft(f"j{i}"))
    assert len(tracker.all_records()) == 5
    assert all(tracker.already_applied(f"j{i}") for i in range(5))


def test_duplicate_job_overwrites(tmp_path):
    tracker = ApplicationTracker(tmp_path / "log.json")
    tracker.record_application(_make_draft("j1", "Old Title"))
    tracker.record_application(_make_draft("j1", "New Title"))
    records = tracker.all_records()
    assert len(records) == 1
    assert records[0]["job_title"] == "New Title"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persists_to_disk_and_reloads(tmp_path):
    log = tmp_path / "log.json"
    tracker = ApplicationTracker(log)
    tracker.record_application(_make_draft("j1"))

    tracker2 = ApplicationTracker(log)
    assert tracker2.already_applied("j1") is True
    assert len(tracker2.all_records()) == 1


def test_loads_existing_json_file(tmp_path):
    log = tmp_path / "log.json"
    log.write_text(
        json.dumps([
            {
                "job_id": "existing",
                "job_title": "SWE",
                "company_name": "OldCo",
                "job_url": "https://example.com",
                "match_score": 90,
                "status": "submitted",
                "submitted_at": "2026-01-01T00:00:00+00:00",
            }
        ])
    )
    tracker = ApplicationTracker(log)
    assert tracker.already_applied("existing") is True
    assert len(tracker.all_records()) == 1


def test_malformed_json_returns_empty(tmp_path):
    log = tmp_path / "log.json"
    log.write_text("{ this is not valid json }")
    tracker = ApplicationTracker(log)
    assert tracker.all_records() == []


def test_missing_log_file_creates_parent_dirs(tmp_path):
    log = tmp_path / "nested" / "deep" / "log.json"
    tracker = ApplicationTracker(log)
    assert tracker.all_records() == []


# ---------------------------------------------------------------------------
# Submitted-at handling
# ---------------------------------------------------------------------------

def test_record_without_submitted_at_uses_now(tmp_path):
    co = Company(id="c1", name="Co", batch="W24", description="d", industry="SaaS")
    job = Job(
        id="j1", url="https://example.com", title="Eng", company=co,
        role_type="backend", description="d", requirements="r",
        location="Remote", remote=True, scraped_at=datetime.now(timezone.utc),
    )
    draft = ApplicationDraft(
        job=job, match_score=80, match_reasoning="ok",
        draft_paragraph="text", status="submitted", submitted_at=None,
    )
    tracker = ApplicationTracker(tmp_path / "log.json")
    tracker.record_application(draft)
    rec = tracker.all_records()[0]
    assert rec["submitted_at"] is not None
    assert len(rec["submitted_at"]) > 0
