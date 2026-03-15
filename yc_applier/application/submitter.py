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
    "button:has-text('Send')",
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

# Selectors for the recruiter/founder name shown in the application form.
# These are tried in order; first match wins.
_RECRUITER_NAME_SELECTORS = [
    # "Send a message to John Smith" / "Message John Smith" headings
    ".application-form h3",
    ".application-form h2",
    "[class*='apply'] h3",
    "[class*='apply'] h2",
    # Name next to founder avatar in the Apply panel
    "[class*='founder'] [class*='name']",
    "[class*='recruiter'] [class*='name']",
    "[class*='contact'] [class*='name']",
    # Image alt text — WaaS often renders "<img alt='Jane Doe'>" for the recruiter
    ".application-form img[alt]",
    "[class*='apply'] img[alt]",
]

def _extract_recruiter_name(page) -> str:
    """Try to find the recruiter/founder name visible in the Apply form."""
    for sel in _RECRUITER_NAME_SELECTORS:
        try:
            el = page.query_selector(sel)
            if not el:
                continue
            # For <img> elements use the alt attribute; otherwise inner text
            tag = page.evaluate("el => el.tagName.toLowerCase()", el)
            if tag == "img":
                name = page.evaluate("el => el.getAttribute('alt')", el) or ""
            else:
                name = el.inner_text().strip()
            # Strip common prefixes like "Message John" → "John", "Apply to John" → "John"
            for prefix in ("send a message to ", "message to ", "message ", "apply to ", "contact "):
                if name.lower().startswith(prefix):
                    name = name[len(prefix):]
            name = name.strip()
            if name and len(name) < 60:   # sanity check — avoid grabbing paragraphs
                logger.debug("Found recruiter name: %s (selector: %s)", name, sel)
                return name
        except Exception:
            continue
    return ""


def _build_email(body: str, recruiter_name: str, user_name: str = "", user_linkedin: str = "") -> str:
    """Wrap the AI-generated body with a greeting and sign-off."""
    first_name = recruiter_name.split()[0] if recruiter_name else ""
    greeting = f"Hi {first_name}," if first_name else "Hi there,"
    sign_off_lines = ["Best Regards,", user_name] if user_name else ["Best Regards,"]
    if user_linkedin:
        sign_off_lines.append(user_linkedin)
    sign_off = "\n".join(sign_off_lines)
    return f"{greeting}\n\n{body}\n\n{sign_off}"


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
            # Use the native HTMLTextAreaElement value setter so React's
            # synthetic onChange fires and controlled-component state updates.
            page.evaluate(
                """([selector, value]) => {
                    const el = document.querySelector(selector);
                    if (!el) return;
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLTextAreaElement.prototype, 'value'
                    ).set;
                    setter.call(el, value);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                [sel, text],
            )
            logger.debug("Filled textarea using selector: %s", sel)
            return True
        except PWTimeoutError:
            continue
    return False


def _click_submit(page) -> bool:
    for sel in _SUBMIT_BUTTON_SELECTORS:
        try:
            # Wait for the button to be visible AND enabled (React may keep it
            # disabled until the textarea has content).
            page.wait_for_selector(f"{sel}:not([disabled])", timeout=5_000)
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
    drafts: list[tuple],   # (ApplicationDraft, user_name: str, user_linkedin: str)
    context: BrowserContext,
    tracker: ApplicationTracker,
    delay_seconds: int = 30,
    dry_run: bool = False,
) -> None:
    """Submit each approved draft and record in the tracker."""
    for draft, user_name, user_linkedin in drafts:
        job = draft.job
        logger.info("Submitting application: %s @ %s", job.title, job.company.name)

        if dry_run:
            email_preview = _build_email(draft.draft_paragraph, "", user_name, user_linkedin)
            logger.info("[DRY RUN] Would submit to %s\n%s", job.url, email_preview)
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

            recruiter_name = _extract_recruiter_name(page)
            if recruiter_name:
                logger.info("Recruiter name found: %s", recruiter_name)
            else:
                logger.info("No recruiter name found — using generic greeting")
            email_text = _build_email(draft.draft_paragraph, recruiter_name, user_name, user_linkedin)

            if not _find_and_fill_textarea(page, email_text):
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
