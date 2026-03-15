"""Scrape job listings from workatastartup.com.

Primary strategy: intercept Algolia API responses triggered by the React SPA.
Fallback: parse visible job cards from the DOM (USE_DOM_FALLBACK=True).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import BrowserContext, Page, Response

from yc_applier.scraper.models import Company, Job

logger = logging.getLogger(__name__)

_JOBS_URL = "https://www.workatastartup.com/jobs"
_ALGOLIA_HOST = "algolia.net"

# Set to True to use DOM parsing instead of Algolia interception.
USE_DOM_FALLBACK = False

# ---------------------------------------------------------------------------
# Algolia interception helpers
# ---------------------------------------------------------------------------

def _is_algolia_response(response: Response) -> bool:
    return _ALGOLIA_HOST in response.url and response.status == 200


def _parse_algolia_hit(hit: dict[str, Any]) -> Job | None:
    try:
        company_data = hit.get("company", {})
        company = Company(
            id=str(company_data.get("id", hit.get("company_id", "unknown"))),
            name=company_data.get("name", hit.get("company_name", "")),
            batch=company_data.get("batch", hit.get("batch", "")),
            description=company_data.get("one_liner", company_data.get("description", "")),
            industry=company_data.get("industry", hit.get("industries", [""])[0] if hit.get("industries") else ""),
            website=company_data.get("website") or hit.get("company_url"),
        )

        job_id = str(hit.get("objectID") or hit.get("id", ""))
        slug = hit.get("slug", job_id)
        url = f"https://www.workatastartup.com/jobs/{slug}"

        return Job(
            id=job_id,
            url=url,
            title=hit.get("title", ""),
            company=company,
            role_type=hit.get("role_type", hit.get("type", "")),
            description=hit.get("job_description", hit.get("description", "")),
            requirements=hit.get("requirements", ""),
            location=hit.get("location", ""),
            remote=bool(hit.get("remote") or hit.get("remote_ok")),
            scraped_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.warning("Skipping malformed Algolia hit: %s — %s", hit.get("objectID"), exc)
        return None


def _collect_algolia_jobs(page: Page, filters: dict) -> list[Job]:
    """Navigate the jobs page with role filters and collect Algolia hits."""
    collected_hits: list[dict] = []

    def handle_response(response: Response) -> None:
        if not _is_algolia_response(response):
            return
        try:
            body = response.json()
            # Multi-query responses wrap results in a "results" array
            result_list = body.get("results", [body])
            for result in result_list:
                hits = result.get("hits", [])
                collected_hits.extend(hits)
        except Exception as exc:
            logger.debug("Non-JSON Algolia response ignored: %s", exc)

    page.on("response", handle_response)

    # Navigate and apply role-type filters via UI clicks
    page.goto(_JOBS_URL, wait_until="networkidle")
    page.wait_for_timeout(2_000)

    role_map = {
        "Full Stack": "fullstack",
        "Backend": "backend",
        "ML": "ml",
    }

    for role in filters.get("roles", []):
        selector_keyword = role_map.get(role, role.lower().replace(" ", "-"))
        # Try checkbox / button selectors for role filter
        for sel in [
            f"label:has-text('{role}')",
            f"[data-value='{selector_keyword}']",
            f"button:has-text('{role}')",
        ]:
            try:
                page.click(sel, timeout=3_000)
                logger.debug("Clicked role filter: %s (%s)", role, sel)
                break
            except Exception:
                continue

    if filters.get("remote_only"):
        for sel in ["label:has-text('Remote')", "[data-value='remote']", "input[value='remote']"]:
            try:
                page.click(sel, timeout=3_000)
                break
            except Exception:
                continue

    # Wait for Algolia to respond after filters are applied
    page.wait_for_timeout(3_000)
    page.off("response", handle_response)

    jobs: list[Job] = []
    seen: set[str] = set()
    for hit in collected_hits:
        job = _parse_algolia_hit(hit)
        if job and job.id not in seen:
            seen.add(job.id)
            jobs.append(job)

    return jobs


# ---------------------------------------------------------------------------
# DOM fallback
# ---------------------------------------------------------------------------

def _collect_dom_jobs(page: Page) -> list[Job]:
    """Parse job cards directly from the DOM as a fallback."""
    page.goto(_JOBS_URL, wait_until="networkidle")
    page.wait_for_timeout(3_000)

    cards = page.query_selector_all(".job-card, [class*='JobCard'], [data-testid='job-card']")
    if not cards:
        logger.warning("DOM fallback: no job cards found with known selectors.")

    jobs: list[Job] = []
    for card in cards:
        try:
            title_el = card.query_selector("h2, h3, [class*='title']")
            title = title_el.inner_text().strip() if title_el else ""

            link_el = card.query_selector("a[href*='/jobs/']")
            href = link_el.get_attribute("href") if link_el else ""
            url = f"https://www.workatastartup.com{href}" if href.startswith("/") else href
            job_id = href.rstrip("/").split("/")[-1]

            company_el = card.query_selector("[class*='company'], [class*='Company']")
            company_name = company_el.inner_text().strip() if company_el else ""

            desc_el = card.query_selector("[class*='description'], p")
            description = desc_el.inner_text().strip() if desc_el else ""

            company = Company(
                id=company_name.lower().replace(" ", "-"),
                name=company_name,
                batch="",
                description="",
                industry="",
            )

            jobs.append(Job(
                id=job_id,
                url=url,
                title=title,
                company=company,
                role_type="",
                description=description,
                requirements="",
                location="",
                remote=False,
                scraped_at=datetime.now(timezone.utc),
            ))
        except Exception as exc:
            logger.warning("DOM fallback: failed to parse card: %s", exc)

    return jobs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_jobs(
    context: BrowserContext,
    filters: dict,
    already_applied: set[str],
    max_jobs: int,
) -> list[Job]:
    """Return up to *max_jobs* new jobs matching *filters*, excluding *already_applied* IDs."""
    page = context.new_page()

    try:
        if USE_DOM_FALLBACK:
            jobs = _collect_dom_jobs(page)
        else:
            jobs = _collect_algolia_jobs(page, filters)
    finally:
        page.close()

    # Post-filter
    filtered: list[Job] = []
    for job in jobs:
        if job.id in already_applied:
            logger.debug("Skipping already-applied job: %s", job.id)
            continue
        if filters.get("remote_only") and not job.remote:
            continue
        excluded = filters.get("excluded_industries", [])
        if excluded and job.company.industry in excluded:
            continue
        filtered.append(job)
        if len(filtered) >= max_jobs:
            break

    logger.info("Scraped %d new jobs (from %d total, %d filtered out).",
                len(filtered), len(jobs), len(jobs) - len(filtered))
    return filtered
