"""Pipeline run, status, and SSE endpoints."""

import asyncio
import json
import os
import threading
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.state import pipeline_state

router = APIRouter()

_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_settings() -> dict:
    with (_PROJECT_ROOT / "config" / "settings.yaml").open() as f:
        return yaml.safe_load(f)


def _draft_to_dict(draft) -> dict:
    job = draft.job
    return {
        "id": job.id,
        "job_id": job.id,
        "job_title": job.title,
        "job_url": job.url,
        "company_name": job.company.name,
        "company_batch": job.company.batch,
        "company_industry": job.company.industry,
        "company_description": job.company.description,
        "role_type": job.role_type,
        "remote": job.remote,
        "location": job.location,
        "match_score": draft.match_score,
        "match_reasoning": draft.match_reasoning,
        "draft_paragraph": draft.draft_paragraph,
        "status": "pending",
    }


def _run_scoring_sync(jobs, resume_text, min_score, api_key, provider):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from yc_applier.ai.matcher import score_jobs
        return loop.run_until_complete(score_jobs(jobs, resume_text, min_score, api_key, provider))
    finally:
        loop.close()


def _run_pipeline_sync(config, email, password, api_key, ai_provider, push_event):
    """Phase 1: scrape + score + draft. Runs in a thread."""
    from playwright.sync_api import sync_playwright
    from yc_applier.auth.login import get_authenticated_context
    from yc_applier.scraper.jobs import scrape_jobs
    from yc_applier.ai.drafter import draft_applications
    from yc_applier.resume.parser import parse_resume
    from yc_applier.storage.tracker import ApplicationTracker

    resume_path = _PROJECT_ROOT / config["paths"]["resume"]
    log_path = _PROJECT_ROOT / config["paths"]["applied_log"]
    session_dir = _PROJECT_ROOT / "data" / "browser_session"

    push_event("progress", "Parsing resume...")
    resume_text = parse_resume(resume_path)
    push_event("progress", f"Resume parsed ({len(resume_text):,} chars)")

    tracker = ApplicationTracker(log_path)
    applied_ids = {r["job_id"] for r in tracker.all_records()}
    push_event("progress", f"Found {len(applied_ids)} already-applied jobs (skipping)")

    push_event("progress", "Launching browser for scraping...")
    with sync_playwright() as pw:
        context = get_authenticated_context(pw, email, password, session_dir)
        push_event("progress", "Authenticated. Scraping jobs...")
        jobs = scrape_jobs(
            context=context,
            filters=config["filters"],
            already_applied=applied_ids,
            max_jobs=config["matching"]["max_jobs_per_run"],
        )
        context.close()

    push_event("progress", f"Found {len(jobs)} new jobs to evaluate")

    if not jobs:
        return []

    push_event("progress", f"Scoring {len(jobs)} jobs with {ai_provider}...")
    scored = _run_scoring_sync(
        jobs, resume_text,
        config["matching"]["min_match_score"],
        api_key, ai_provider,
    )
    push_event("progress", f"{len(scored)} jobs passed the match threshold (≥{config['matching']['min_match_score']})")

    if not scored:
        return []

    push_event("progress", f"Drafting {len(scored)} application paragraphs...")
    drafts = draft_applications(scored, resume_text, api_key, ai_provider)
    push_event("progress", f"Generated {len(drafts)} drafts — ready for review")

    return drafts


def _run_submit_sync(approved_drafts_data, dry_run, email, password, push_event):
    """Phase 2: submit approved drafts. Runs in a thread."""
    from datetime import datetime
    from playwright.sync_api import sync_playwright
    from yc_applier.auth.login import get_authenticated_context
    from yc_applier.storage.tracker import ApplicationTracker
    from yc_applier.scraper.models import ApplicationDraft, Job, Company
    from yc_applier.application.submitter import submit_applications

    cfg = _load_settings()
    log_path = _PROJECT_ROOT / cfg["paths"]["applied_log"]
    session_dir = _PROJECT_ROOT / "data" / "browser_session"
    tracker = ApplicationTracker(log_path)

    draft_objects = []
    for d in approved_drafts_data:
        company = Company(
            id=d.get("company_name", "unknown"),
            name=d["company_name"],
            batch=d.get("company_batch", ""),
            description=d.get("company_description", ""),
            industry=d.get("company_industry", ""),
        )
        job = Job(
            id=d["job_id"],
            url=d["job_url"],
            title=d["job_title"],
            company=company,
            role_type=d.get("role_type", ""),
            description="",
            requirements="",
            location=d.get("location", ""),
            remote=d.get("remote", False),
            scraped_at=datetime.utcnow(),
        )
        draft = ApplicationDraft(
            job=job,
            match_score=d["match_score"],
            match_reasoning=d.get("match_reasoning", ""),
            draft_paragraph=d["draft_paragraph"],
            status="approved",
        )
        draft_objects.append(draft)

    push_event("progress", f"Submitting {len(draft_objects)} application(s)...")
    with sync_playwright() as pw:
        context = get_authenticated_context(pw, email, password, session_dir)
        submit_applications(
            drafts=draft_objects,
            context=context,
            tracker=tracker,
            delay_seconds=cfg["behavior"]["application_delay_seconds"],
            dry_run=dry_run,
        )
        context.close()

    push_event("progress", "Submission complete!")


class StartPipelineRequest(BaseModel):
    dry_run: bool = False
    ai_provider: str = "anthropic"


class SubmitRequest(BaseModel):
    dry_run: bool = False


@router.post("/start")
async def start_pipeline(req: StartPipelineRequest):
    with pipeline_state._lock:
        if pipeline_state.status in ("running", "submitting"):
            raise HTTPException(status_code=400, detail="Pipeline already running")
        # Reset fields directly — calling pipeline_state.reset() here would deadlock
        # because reset() also acquires _lock (non-reentrant).
        pipeline_state.status = "running"
        pipeline_state.progress = []
        pipeline_state.drafts = []
        pipeline_state.error = None

    config = _load_settings()
    email = os.environ.get("YC_EMAIL", "")
    password = os.environ.get("YC_PASSWORD", "")
    api_key = (
        os.environ.get("OPENAI_API_KEY", "")
        if req.ai_provider == "openai"
        else os.environ.get("ANTHROPIC_API_KEY", "")
    )

    def run():
        try:
            drafts = _run_pipeline_sync(
                config, email, password, api_key, req.ai_provider,
                pipeline_state.push_event,
            )
            with pipeline_state._lock:
                pipeline_state.drafts = [_draft_to_dict(d) for d in drafts]
                pipeline_state.status = "awaiting_review" if drafts else "complete"
            msg = (
                f"Pipeline complete — {len(drafts)} drafts ready for review"
                if drafts else "Pipeline complete — no drafts generated"
            )
            pipeline_state.push_event("status_change", msg)
        except Exception as exc:
            with pipeline_state._lock:
                pipeline_state.status = "error"
                pipeline_state.error = str(exc)
            pipeline_state.push_event("error", str(exc))

    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}


@router.post("/submit")
async def submit_pipeline(req: SubmitRequest):
    with pipeline_state._lock:
        if pipeline_state.status not in ("awaiting_review", "complete"):
            raise HTTPException(status_code=400, detail="Pipeline not in reviewable state")
        approved = [d for d in pipeline_state.drafts if d.get("status") == "approved"]
        if not approved:
            raise HTTPException(status_code=400, detail="No approved drafts to submit")
        pipeline_state.status = "submitting"

    email = os.environ.get("YC_EMAIL", "")
    password = os.environ.get("YC_PASSWORD", "")

    def run():
        try:
            _run_submit_sync(approved, req.dry_run, email, password, pipeline_state.push_event)
            with pipeline_state._lock:
                for d in pipeline_state.drafts:
                    if d.get("status") == "approved":
                        d["status"] = "submitted"
                pipeline_state.status = "complete"
            pipeline_state.push_event("status_change", "All applications submitted!")
        except Exception as exc:
            with pipeline_state._lock:
                pipeline_state.status = "error"
                pipeline_state.error = str(exc)
            pipeline_state.push_event("error", str(exc))

    threading.Thread(target=run, daemon=True).start()
    return {"status": "submitting"}


@router.get("/status")
def get_status():
    return pipeline_state.to_dict()


@router.get("/events")
async def pipeline_events():
    queue: asyncio.Queue = asyncio.Queue()
    pipeline_state.add_sse_queue(queue)

    async def generator():
        try:
            yield f"data: {json.dumps({'type': 'init', 'status': pipeline_state.status})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            pipeline_state.remove_sse_queue(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
