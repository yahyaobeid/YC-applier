"""CLI entry point for yc-applier."""

import asyncio
import concurrent.futures
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

app = typer.Typer(name="yc-apply", add_completion=False, pretty_exceptions_short=True)
console = Console()

_PROJECT_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


def _load_settings() -> dict:
    with _SETTINGS_PATH.open() as f:
        return yaml.safe_load(f)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


# ---------------------------------------------------------------------------
# yc-apply run
# ---------------------------------------------------------------------------

@app.command()
def run(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Scrape + score + draft, skip submission.")] = False,
    no_review: Annotated[bool, typer.Option("--no-review", help="Skip interactive review; only auto-apply.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    ai_provider: Annotated[str, typer.Option("--ai-provider", help="AI provider to use: 'anthropic' or 'openai'.")] = "anthropic",
) -> None:
    """Run the full YC job application pipeline."""
    _setup_logging(verbose)
    cfg = _load_settings()

    if ai_provider not in ("anthropic", "openai"):
        console.print("[red]--ai-provider must be 'anthropic' or 'openai'[/red]")
        raise typer.Exit(1)

    # Env vars
    email = os.environ.get("YC_EMAIL", "")
    password = os.environ.get("YC_PASSWORD", "")

    if ai_provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            console.print("[red]OPENAI_API_KEY not set in environment / .env[/red]")
            raise typer.Exit(1)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            console.print("[red]ANTHROPIC_API_KEY not set in environment / .env[/red]")
            raise typer.Exit(1)
    if not dry_run and (not email or not password):
        console.print("[red]YC_EMAIL and YC_PASSWORD must be set for live runs.[/red]")
        raise typer.Exit(1)

    # Resolve paths
    resume_path = _PROJECT_ROOT / cfg["paths"]["resume"]
    log_path = _PROJECT_ROOT / cfg["paths"]["applied_log"]
    session_dir = _PROJECT_ROOT / "data" / "browser_session"

    # 1. Parse resume
    from yc_applier.resume.parser import parse_resume
    console.print("[bold]Parsing resume…[/bold]")
    resume_text = parse_resume(resume_path)
    console.print(f"[green]Resume parsed[/green] ({len(resume_text):,} chars)")

    # 2. Load tracker / dedup set
    from yc_applier.storage.tracker import ApplicationTracker
    tracker = ApplicationTracker(log_path)
    applied_ids: set[str] = {r["job_id"] for r in tracker.all_records()}
    console.print(f"Already applied to [cyan]{len(applied_ids)}[/cyan] jobs (will skip).")

    # 3. Scrape jobs
    from playwright.sync_api import sync_playwright
    from yc_applier.auth.login import get_authenticated_context
    from yc_applier.scraper.jobs import scrape_jobs

    console.print("[bold]Launching browser…[/bold]")
    with sync_playwright() as pw:
        context = get_authenticated_context(pw, email, password, session_dir)

        console.print("[bold]Scraping jobs…[/bold]")
        jobs = scrape_jobs(
            context=context,
            filters=cfg["filters"],
            already_applied=applied_ids,
            max_jobs=cfg["matching"]["max_jobs_per_run"],
        )
        console.print(f"Found [cyan]{len(jobs)}[/cyan] new jobs to evaluate.")

        if not jobs:
            console.print("[yellow]No new jobs found. Exiting.[/yellow]")
            return

        # 4. Score jobs with AI
        # Run in a thread because Playwright 1.58+ holds an asyncio loop on the main thread
        console.print(f"[bold]Scoring jobs with {ai_provider}…[/bold]")
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            scored = pool.submit(
                _run_scoring_sync, jobs, resume_text,
                cfg["matching"]["min_match_score"], api_key, ai_provider
            ).result()
        console.print(f"[cyan]{len(scored)}[/cyan] jobs passed the match threshold "
                      f"(≥{cfg['matching']['min_match_score']}).")

        if not scored:
            console.print("[yellow]No jobs met the score threshold. Exiting.[/yellow]")
            return

        # 5. Draft application paragraphs
        from yc_applier.ai.drafter import draft_applications
        console.print("[bold]Drafting application paragraphs…[/bold]")
        drafts = draft_applications(scored, resume_text, api_key, ai_provider)

        # 6. Review
        from yc_applier.application.reviewer import review_drafts
        behavior = cfg["behavior"]
        review_mode = behavior["review_mode"] and not no_review

        if review_mode:
            console.print("\n[bold]Starting interactive review…[/bold]\n")
            approved_drafts = review_drafts(drafts, behavior["auto_apply_above_score"])
        else:
            # No review: only submit auto-qualify jobs
            threshold = behavior["auto_apply_above_score"]
            approved_drafts = []
            for d in drafts:
                if d.match_score >= threshold:
                    d.status = "auto_approved"
                    approved_drafts.append(d)
            console.print(
                f"No-review mode: [cyan]{len(approved_drafts)}[/cyan] jobs auto-approved "
                f"(score ≥ {threshold})."
            )

        console.print(f"\n[bold]{len(approved_drafts)}[/bold] application(s) approved for submission.")

        if not approved_drafts:
            return

        # 7. Submit
        from yc_applier.application.submitter import submit_applications
        submit_applications(
            drafts=approved_drafts,
            context=context,
            tracker=tracker,
            delay_seconds=behavior["application_delay_seconds"],
            dry_run=dry_run,
        )

        context.close()

    console.print("[bold green]Done![/bold green]")


def _run_scoring_sync(jobs, resume_text, min_score, api_key, provider="anthropic"):
    """Run async scoring in a fresh event loop (called from a worker thread)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from yc_applier.ai.matcher import score_jobs
        return loop.run_until_complete(score_jobs(jobs, resume_text, min_score, api_key, provider))
    finally:
        loop.close()


async def _score_jobs_async(jobs, resume_text, min_score, api_key, provider="anthropic"):
    from yc_applier.ai.matcher import score_jobs
    return await score_jobs(jobs, resume_text, min_score, api_key, provider)


# ---------------------------------------------------------------------------
# yc-apply list-applied
# ---------------------------------------------------------------------------

@app.command(name="list-applied")
def list_applied(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Show the applied jobs audit log as a table."""
    _setup_logging(verbose)
    cfg = _load_settings()
    log_path = _PROJECT_ROOT / cfg["paths"]["applied_log"]

    from yc_applier.storage.tracker import ApplicationTracker
    tracker = ApplicationTracker(log_path)
    records = tracker.all_records()

    if not records:
        console.print("[yellow]No applications on record.[/yellow]")
        return

    table = Table(title=f"Applied Jobs ({len(records)} total)", show_lines=True)
    table.add_column("Company", style="cyan")
    table.add_column("Title")
    table.add_column("Score", justify="right")
    table.add_column("Status", style="green")
    table.add_column("Submitted At")

    for rec in sorted(records, key=lambda r: r.get("submitted_at", ""), reverse=True):
        table.add_row(
            rec.get("company_name", ""),
            rec.get("job_title", ""),
            str(rec.get("match_score", "")),
            rec.get("status", ""),
            rec.get("submitted_at", "")[:19],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# yc-apply clear-session
# ---------------------------------------------------------------------------

@app.command(name="clear-session")
def clear_session(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete the saved browser session, forcing a fresh login on next run."""
    _setup_logging(verbose)
    session_dir = _PROJECT_ROOT / "data" / "browser_session"
    from yc_applier.auth.login import clear_session as _clear
    _clear(session_dir)
    console.print("[green]Session cleared.[/green]")


if __name__ == "__main__":
    app()
