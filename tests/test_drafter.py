"""Tests for ai/drafter.py."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from yc_applier.scraper.models import ApplicationDraft, Company, Job
from yc_applier.ai.drafter import draft_applications


def _make_scored_job(job_id: str = "j1") -> tuple:
    job = Job(
        id=job_id,
        url=f"https://www.workatastartup.com/jobs/{job_id}",
        title="Full Stack Engineer",
        company=Company(
            id="c1",
            name="TechCo",
            batch="S23",
            description="Fintech startup",
            industry="Fintech",
        ),
        role_type="fullstack",
        description="Build features end-to-end",
        requirements="React, Python, PostgreSQL",
        location="Remote",
        remote=True,
        scraped_at=datetime.now(timezone.utc),
    )
    return (job, 82, "Strong match on full stack skills")


def _mock_claude_response(text: str) -> MagicMock:
    content = MagicMock()
    content.text = f"  {text}  "  # include whitespace to test stripping
    response = MagicMock()
    response.content = [content]
    return response


def test_draft_applications_returns_drafts():
    scored = [_make_scored_job("j1"), _make_scored_job("j2")]
    paragraph = "I bring 5 years of full-stack experience to this role."
    mock_create = MagicMock(return_value=_mock_claude_response(paragraph))

    with patch("yc_applier.ai.drafter.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_cls.return_value = mock_client

        drafts = draft_applications(scored, "resume text", api_key="test-key")

    assert len(drafts) == 2
    for draft in drafts:
        assert isinstance(draft, ApplicationDraft)
        assert draft.draft_paragraph == paragraph
        assert draft.status == "pending_review"
        assert draft.match_score > 0


def test_draft_applications_strips_whitespace():
    scored = [_make_scored_job()]
    mock_create = MagicMock(return_value=_mock_claude_response("  Some paragraph.  "))

    with patch("yc_applier.ai.drafter.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_cls.return_value = mock_client

        drafts = draft_applications(scored, "resume", api_key="test-key")

    assert drafts[0].draft_paragraph == "Some paragraph."


def test_draft_applications_handles_api_error():
    """If Claude fails, paragraph should be empty string (no exception raised)."""
    scored = [_make_scored_job()]

    with patch("yc_applier.ai.drafter.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_client_cls.return_value = mock_client

        # Patch tenacity to not retry in tests
        with patch("yc_applier.ai.drafter._draft_paragraph", side_effect=Exception("API error")):
            drafts = draft_applications(scored, "resume", api_key="test-key")

    assert len(drafts) == 1
    assert drafts[0].draft_paragraph == ""
