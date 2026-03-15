"""Playwright-based form submission.

IMPORTANT: The selectors below are best-guess approximations.
Before using this in production, log into workatastartup.com in a browser,
navigate to a job listing, inspect the application form, and update the
constants below to match the live selectors.
"""

import logging
import time
from datetime import datetime, timezone

from playwright.sync_api import BrowserContext, TimeoutError as PWTimeoutError

from yc_applier.scraper.models import ApplicationDraft
from yc_applier.storage.tracker import ApplicationTracker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Selectors — verify against live site before using
# ---------------------------------------------------------------------------
# "Apply" opener — an <a> tag that reveals the application textarea
_APPLY_BUTTON_SELECTORS = [
    "a:has-text('Apply')",
    "button:has-text('Apply')",
]

# The application textarea (visible after clicking Apply)
_TEXTAREA_SELECTORS = [
    "textarea[placeholder*='My name is']",
    "textarea[placeholder*='name is']",
    "textarea[rows='7']",
    "textarea",                           # last resort: first textarea on page
]

# The submit button inside the expanded form
_SUBMIT_BUTTON_SELECTORS = [
    "button[type='submit']:has-text('Apply')",
    "button:has-text('Submit application')",
    "button:has-text('Submit')",
    "button:has-text('Apply')",
    "input[type='submit']",
]

# Element that signals a successful submission
_SUCCESS_SELECTORS = [
    "[data-testid='application-success']",
    "text=Application submitted",
    "text=applied successfully",
    "text=Applied",
    ".success-message",
]


def _open_apply_form(page) -> bool:
    """Click the Apply button to reveal the application textarea."""
    for sel in _APPLY_BUTTON_SELECTORS:
        try:
            page.click(sel, timeout=5_000)
            logger.debug("Clicked Apply opener using selector: %s", sel)
            return True
        except PWTimeoutError:
            continue
    return False


def _find_and_fill_textarea(page, text: str) -> bool:
    for sel in _TEXTAREA_SELECTORS:
        try:
            page.wait_for_selector(sel, timeout=5_000)
            page.fill(sel, text)
            logger.debug("Filled textarea using selector: %s", sel)
            return True
        except PWTimeoutError:
            continue
    return False


def _click_submit(page) -> bool:
    for sel in _SUBMIT_BUTTON_SELECTORS:
        try:
            page.click(sel, timeout=4_000)
            logger.debug("Clicked submit using selector: %s", sel)
            return True
        except PWTimeoutError:
            continue
    return False


def _wait_for_success(page) -> bool:
    for sel in _SUCCESS_SELECTORS:
        try:
            page.wait_for_selector(sel, timeout=8_000)
            logger.debug("Success indicator found: %s", sel)
            return True
        except PWTimeoutError:
            continue
    return False


def submit_applications(
    drafts: list[ApplicationDraft],
    context: BrowserContext,
    tracker: ApplicationTracker,
    delay_seconds: int = 30,
    dry_run: bool = False,
) -> None:
    """Submit each approved draft and record in the tracker."""
    for draft in drafts:
        job = draft.job
        logger.info("Submitting application: %s @ %s", job.title, job.company.name)

        if dry_run:
            logger.info("[DRY RUN] Would submit to %s", job.url)
            draft.status = "submitted"
            draft.submitted_at = datetime.now(timezone.utc)
            tracker.record_application(draft)
            continue

        page = context.new_page()
        try:
            page.goto(job.url, wait_until="networkidle")
            page.wait_for_timeout(1_500)

            # Click the Apply <a> button to reveal the textarea
            if not _open_apply_form(page):
                logger.warning("Could not find Apply button on %s — trying textarea directly.", job.url)

            page.wait_for_timeout(1_000)

            if not _find_and_fill_textarea(page, draft.draft_paragraph):
                logger.error(
                    "Could not find application textarea on %s — skipping. "
                    "Update _TEXTAREA_SELECTORS after inspecting the live page.",
                    job.url,
                )
                continue

            if not _click_submit(page):
                logger.error(
                    "Could not find submit button on %s — skipping. "
                    "Update _SUBMIT_BUTTON_SELECTORS after inspecting the live page.",
                    job.url,
                )
                continue

            success = _wait_for_success(page)
            if success:
                draft.status = "submitted"
                draft.submitted_at = datetime.now(timezone.utc)
                tracker.record_application(draft)
                logger.info("Successfully submitted: %s @ %s", job.title, job.company.name)
            else:
                logger.warning(
                    "Submitted to %s but could not confirm success. "
                    "Check the page manually. Recording as submitted anyway.",
                    job.url,
                )
                draft.status = "submitted"
                draft.submitted_at = datetime.now(timezone.utc)
                tracker.record_application(draft)

        except Exception as exc:
            logger.error("Error submitting to %s: %s", job.url, exc)
        finally:
            page.close()

        if delay_seconds > 0:
            logger.info("Waiting %ds before next submission…", delay_seconds)
            time.sleep(delay_seconds)
