"""Tests for ai/matcher.py."""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from yc_applier.scraper.models import Company, Job
from yc_applier.ai.matcher import score_jobs


def _make_job(job_id: str = "j1", title: str = "Backend Engineer") -> Job:
    return Job(
        id=job_id,
        url=f"https://www.workatastartup.com/jobs/{job_id}",
        title=title,
        company=Company(
            id="c1",
            name="Acme Corp",
            batch="W24",
            description="We build cool things",
            industry="SaaS",
        ),
        role_type="backend",
        description="Build scalable APIs",
        requirements="Python, AWS",
        location="Remote",
        remote=True,
        scraped_at=datetime.now(timezone.utc),
    )


def _mock_response(score: int, reasoning: str = "Good match") -> MagicMock:
    content = MagicMock()
    content.text = json.dumps({
        "score": score,
        "reasoning": reasoning,
        "key_matches": ["Python"],
        "gaps": [],
    })
    response = MagicMock()
    response.content = [content]
    return response


@pytest.mark.asyncio
async def test_score_jobs_above_threshold():
    job = _make_job()
    mock_create = AsyncMock(return_value=_mock_response(85))

    with patch("yc_applier.ai.matcher.anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_cls.return_value = mock_client

        results = await score_jobs([job], "resume text", min_score=70, api_key="test-key")

    assert len(results) == 1
    assert results[0][1] == 85


@pytest.mark.asyncio
async def test_score_jobs_below_threshold_filtered_out():
    job = _make_job()
    mock_create = AsyncMock(return_value=_mock_response(50))

    with patch("yc_applier.ai.matcher.anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_cls.return_value = mock_client

        results = await score_jobs([job], "resume text", min_score=70, api_key="test-key")

    assert len(results) == 0


@pytest.mark.asyncio
async def test_score_jobs_sorted_by_score_desc():
    jobs = [_make_job("j1", "Role A"), _make_job("j2", "Role B"), _make_job("j3", "Role C")]

    responses = [
        _mock_response(75),
        _mock_response(95),
        _mock_response(80),
    ]
    call_count = 0

    async def side_effect(**kwargs):
        nonlocal call_count
        r = responses[call_count % len(responses)]
        call_count += 1
        return r

    with patch("yc_applier.ai.matcher.anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=side_effect)
        mock_client_cls.return_value = mock_client

        results = await score_jobs(jobs, "resume", min_score=70, api_key="test-key")

    scores = [r[1] for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_score_jobs_bad_json_returns_zero():
    job = _make_job()
    bad_content = MagicMock()
    bad_content.text = "not json at all"
    bad_response = MagicMock()
    bad_response.content = [bad_content]
    mock_create = AsyncMock(return_value=bad_response)

    with patch("yc_applier.ai.matcher.anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_client_cls.return_value = mock_client

        results = await score_jobs([job], "resume", min_score=0, api_key="test-key")

    assert len(results) == 1
    assert results[0][1] == 0
