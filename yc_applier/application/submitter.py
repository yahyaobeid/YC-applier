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
# "Apply" opener — an <a> tag that reveals the application textarea.
# Use the orange button class to avoid matching nav/other links.
_APPLY_BUTTON_SELECTORS = [
    "a.bg-orange-500:has-text('Apply')",
    "a:has-text('Apply')",
    "button.bg-orange-500:has-text('Apply')",
    "button:has-text('Apply')",
]

# The application textarea (visible after clicking Apply)
_TEXTAREA_SELECTORS = [
    # Most WaaS jobs render a React-controlled textarea inside the "Apply" dialog.
    "textarea[placeholder*='My name is']",
    "textarea[placeholder*='name is']",
    "textarea[placeholder*='message']",
    "textarea[aria-label*='message']",
    # Scope to the dialog when possible.
    "[role='dialog'] textarea",
    # Last resort: any textarea on the page (we relax "visible" waits below).
    "textarea",
]

# Some React UIs use a contenteditable div instead of a textarea.
_CONTENTEDITABLE_SELECTORS = [
    "[role='dialog'] [contenteditable='true']",
    "[contenteditable='true']",
]

# The submit button inside the expanded form.
# On workatastartup.com this is <button ... disabled="">Send</button> — starts
# disabled until React sees textarea input.
_SUBMIT_BUTTON_SELECTORS = [
    "button.bg-orange-500:has-text('Send')",
    "button:has-text('Send')",
    "button[type='submit']",
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

def _log_page_debug_facts(page, label: str) -> None:
    """Emit lightweight DOM facts to understand where the bot is stuck."""
    try:
        dialog_count = len(page.query_selector_all("[role='dialog']"))
    except Exception:
        dialog_count = -1
    try:
        textarea_count = len(page.query_selector_all("textarea"))
    except Exception:
        textarea_count = -1
    try:
        contenteditable_count = len(page.query_selector_all("[contenteditable='true']"))
    except Exception:
        contenteditable_count = -1
    try:
        enabled_send_count = len(page.query_selector_all("button:has-text('Send'):not([disabled])"))
    except Exception:
        enabled_send_count = -1

    logger.debug(
        "[%s] url=%s dialog=%s textarea=%s contenteditable=%s enabled_send=%s",
        label,
        getattr(page, "url", ""),
        dialog_count,
        textarea_count,
        contenteditable_count,
        enabled_send_count,
    )


def _preview(text: str, limit: int = 90) -> str:
    text = text or ""
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


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
    greeting = f"Hi {first_name}," if first_name else "Hello,"
    sign_off_lines = ["Best Regards,", user_name] if user_name else ["Best Regards,"]
    if user_linkedin:
        sign_off_lines.append(user_linkedin)
    sign_off = "\n".join(sign_off_lines)
    return f"{greeting}\n\n{body}\n\n{sign_off}"


def _open_apply_form(page) -> bool:
    """Click the Apply button and wait for the dialog/textarea to appear."""
    start = time.monotonic()
    logger.info("Opening Apply form (url=%s)", getattr(page, "url", ""))
    for sel in _APPLY_BUTTON_SELECTORS:
        try:
            logger.debug("Trying Apply opener selector: %s", sel)
            _log_page_debug_facts(page, f"before-click-apply:{sel}")
            page.click(sel, timeout=5_000)
            logger.debug("Clicked Apply opener using selector: %s", sel)
            # Wait for a textarea OR contenteditable to appear (may or may
            # not be inside a [role="dialog"] — the site uses both patterns).
            try:
                page.wait_for_selector(
                    'textarea, [contenteditable="true"]',
                    timeout=8_000,
                    state="attached",
                )
                logger.debug("Apply form input detected (textarea or contenteditable)")
            except PWTimeoutError:
                logger.debug("No textarea/contenteditable appeared after click — will retry next selector")
            except Exception as exc:
                logger.debug("Error while waiting for form input: %s", exc)
            _log_page_debug_facts(page, f"after-click-apply:{sel}")
            logger.info("Apply opener clicked successfully in %.2fs", time.monotonic() - start)
            return True
        except PWTimeoutError:
            logger.debug("Timed out clicking Apply opener selector: %s", sel)
            continue
        except Exception as exc:
            logger.debug("Failed clicking Apply opener selector %s: %s", sel, exc)
            continue
    logger.warning("Failed to find/click Apply opener after %.2fs", time.monotonic() - start)
    return False


def _find_and_fill_textarea(page, text: str) -> bool:
    start = time.monotonic()
    logger.info("Filling application message input (len=%s preview=%r)", len(text or ""), _preview(text))
    for sel in _TEXTAREA_SELECTORS:
        try:
            # On this site the textarea may exist before it becomes "visible"
            # (React animates the dialog). Use "attached" to avoid false negatives.
            logger.debug("Waiting for textarea selector (attached): %s", sel)
            _log_page_debug_facts(page, f"before-wait-textarea:{sel}")
            el = page.wait_for_selector(sel, timeout=5_000, state="attached")
            if not el:
                continue
            try:
                tag = el.evaluate("el => el.tagName.toLowerCase()")
            except Exception:
                tag = "unknown"
            logger.debug("Found input element for selector=%s tag=%s", sel, tag)
            # Best-effort focus/click. Some controlled components enable the Send
            # button only after input events; we also dispatch `input` below.
            try:
                el.scroll_into_view_if_needed(timeout=2_000)
            except Exception:
                pass
            try:
                el.click(timeout=2_000, force=True)
            except Exception:
                # Click isn't strictly required if we can set value + dispatch input.
                pass
            # Use React's native value setter so the controlled component's
            # onChange fires and React state is updated (enabling the Send button).
            # keyboard.type() bypasses React's synthetic event system on controlled
            # inputs, leaving React's internal state empty and the button disabled.
            # el.evaluate(js, arg) passes the element as the first JS arg and
            # arg as the second — cleaner than page.evaluate with an array.
            el.evaluate(
                """(el, val) => {
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLTextAreaElement.prototype, 'value'
                    ).set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                text,
            )
            logger.debug("Filled textarea via React native setter using selector: %s", sel)
            _log_page_debug_facts(page, f"after-fill-textarea:{sel}")
            logger.info("Message input filled using textarea selectors in %.2fs", time.monotonic() - start)
            return True
        except PWTimeoutError:
            logger.debug("Textarea selector not found before timeout: %s", sel)
            continue
        except Exception as exc:
            logger.debug("Textarea fill failed for selector %s: %s", sel, exc)
            continue

    # Fallback: contenteditable region
    for sel in _CONTENTEDITABLE_SELECTORS:
        try:
            logger.debug("Waiting for contenteditable selector (attached): %s", sel)
            _log_page_debug_facts(page, f"before-wait-contenteditable:{sel}")
            el = page.wait_for_selector(sel, timeout=5_000, state="attached")
            if not el:
                continue
            try:
                el.scroll_into_view_if_needed(timeout=2_000)
            except Exception:
                pass
            try:
                el.click(timeout=2_000, force=True)
            except Exception:
                pass

            el.evaluate(
                """(el, val) => {
                    // Best-effort: set text content and dispatch input so React can update.
                    el.focus?.();
                    el.textContent = val;
                    el.dispatchEvent(new InputEvent('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                text,
            )
            logger.debug("Filled contenteditable region using selector: %s", sel)
            _log_page_debug_facts(page, f"after-fill-contenteditable:{sel}")
            logger.info("Message input filled using contenteditable selectors in %.2fs", time.monotonic() - start)
            return True
        except PWTimeoutError:
            logger.debug("Contenteditable selector not found before timeout: %s", sel)
            continue
        except Exception as exc:
            logger.debug("contenteditable fill failed for selector %s: %s", sel, exc)
            continue

    logger.warning("Failed to fill message input after %.2fs", time.monotonic() - start)
    return False


def _click_submit(page) -> bool:
    start = time.monotonic()
    logger.info("Clicking submit (url=%s)", getattr(page, "url", ""))
    for sel in _SUBMIT_BUTTON_SELECTORS:
        try:
            logger.debug("Trying submit selector: %s", sel)
            _log_page_debug_facts(page, f"before-wait-submit:{sel}")
            # Wait up to 10 s for React to enable the button after textarea input.
            # Re-query rather than reusing a handle to avoid stale element refs
            # after React re-renders the button when it becomes enabled.
            el = page.wait_for_selector(f"{sel}:not([disabled])", timeout=10_000)
            if not el:
                continue
            # Re-query to get a fresh reference after the wait
            el = page.query_selector(f"{sel}:not([disabled])")
            if not el:
                continue
            try:
                logger.debug("Submit element attributes: %s", el.evaluate("el => ({tag: el.tagName, type: el.type, text: el.innerText})"))
            except Exception:
                pass
            el.click(timeout=2_000)
            logger.debug("Clicked submit using selector: %s", sel)
            _log_page_debug_facts(page, f"after-click-submit:{sel}")
            logger.info("Submit clicked successfully in %.2fs", time.monotonic() - start)
            return True
        except PWTimeoutError:
            logger.debug("Submit button selector never became enabled in timeout: %s", sel)
            continue
        except Exception as exc:
            logger.debug("Failed clicking submit using selector %s: %s", sel, exc)
            continue
    # NOTE: We intentionally do NOT force-enable a disabled button here.
    # If the Send button is still disabled, it means React's internal state
    # wasn't updated (textarea fill failed), and submitting would send a blank form.
    logger.warning("Could not click enabled submit button after %.2fs", time.monotonic() - start)
    return False


def _wait_for_success(page) -> bool:
    start = time.monotonic()
    # On workatastartup.com the send form is a React SPA dialog — no page
    # navigation occurs. Success is indicated by the dialog closing, which
    # removes the textarea/contenteditable region from the DOM.
    logger.info("Waiting for success indicator (url=%s)", getattr(page, "url", ""))
    _log_page_debug_facts(page, "before-wait-success")
    try:
        logger.debug("Waiting for textarea detached from DOM (timeout=8s)")
        page.wait_for_selector("textarea", state="detached", timeout=8_000)
        logger.debug("Success: textarea detached from DOM (dialog closed after send)")
        logger.info("Success confirmed in %.2fs (textarea detached)", time.monotonic() - start)
        return True
    except PWTimeoutError:
        logger.debug("Textarea did not detach within timeout (8s)")
        pass
    except Exception as exc:
        logger.debug("Unexpected error while waiting textarea detached: %s", exc)
        pass

    try:
        logger.debug("Waiting for contenteditable detached from DOM (timeout=2s)")
        page.wait_for_selector("[contenteditable='true']", state="detached", timeout=2_000)
        logger.debug("Success: contenteditable detached from DOM (dialog closed after send)")
        logger.info("Success confirmed in %.2fs (contenteditable detached)", time.monotonic() - start)
        return True
    except PWTimeoutError:
        logger.debug("Contenteditable did not detach within timeout (2s)")
        pass
    except Exception as exc:
        logger.debug("Unexpected error while waiting contenteditable detached: %s", exc)
        pass
    # Fallback: check for any explicit success text that may appear
    for sel in _SUCCESS_SELECTORS:
        try:
            logger.debug("Waiting for success selector: %s (timeout=2s)", sel)
            page.wait_for_selector(sel, timeout=2_000)
            logger.debug("Success indicator found: %s", sel)
            logger.info("Success confirmed in %.2fs (success selector matched)", time.monotonic() - start)
            return True
        except PWTimeoutError:
            logger.debug("Success selector not found within timeout: %s", sel)
            continue
        except Exception as exc:
            logger.debug("Error while waiting success selector %s: %s", sel, exc)
            continue
    logger.warning("No success indicator detected after %.2fs", time.monotonic() - start)
    return False


def submit_applications(
    drafts: list[tuple],   # (ApplicationDraft, user_name: str, user_linkedin: str)
    context: BrowserContext,
    tracker: ApplicationTracker,
    delay_seconds: int = 30,
    dry_run: bool = False,
    push_event=None,
) -> None:
    """Submit each approved draft and record in the tracker."""
    def _emit(msg):
        if push_event:
            push_event("progress", msg)

    for idx, (draft, user_name, user_linkedin) in enumerate(drafts, start=1):
        job = draft.job
        logger.info("Submitting application %d/%d: %s @ %s", idx, len(drafts), job.title, job.company.name)
        _emit(f"[{idx}/{len(drafts)}] Submitting to {job.company.name} — {job.title}…")
        logger.info("Job url=%s (draft.status=%s)", job.url, getattr(draft, "status", "unknown"))

        if dry_run:
            email_preview = _build_email(draft.draft_paragraph, "", user_name, user_linkedin)
            logger.info("[DRY RUN] Would submit to %s\n%s", job.url, email_preview)
            draft.status = "submitted"
            draft.submitted_at = datetime.now(timezone.utc)
            tracker.record_application(draft)
            continue

        page = context.new_page()
        try:
            logger.info("Navigating to job page...")
            # Use domcontentloaded — networkidle hangs on SPAs with persistent
            # connections (websockets, analytics, etc.)
            page.goto(job.url, wait_until="domcontentloaded", timeout=30_000)
            logger.info("Navigation complete. Current url=%s", getattr(page, "url", ""))
            # Give React a moment to hydrate and render the Apply button
            page.wait_for_timeout(3_000)
            _log_page_debug_facts(page, "after-goto")

            # Click the Apply <a> button to reveal the textarea.
            # _open_apply_form already waits for the dialog to open internally.
            if not _open_apply_form(page):
                logger.warning("Could not find Apply button on %s — trying textarea directly.", job.url)
            _log_page_debug_facts(page, "after-open-apply")

            recruiter_name = _extract_recruiter_name(page)
            if recruiter_name:
                logger.info("Recruiter name found: %s", recruiter_name)
            else:
                logger.info("No recruiter name found — using generic greeting")
            email_text = _build_email(draft.draft_paragraph, recruiter_name, user_name, user_linkedin)
            logger.debug("Built email text preview=%r len=%d", _preview(email_text), len(email_text))

            if not _find_and_fill_textarea(page, email_text):
                logger.error(
                    "Could not find application textarea on %s — skipping. "
                    "Update _TEXTAREA_SELECTORS after inspecting the live page.",
                    job.url,
                )
                continue

            # Wait for the site to finish processing the pasted text before
            # attempting to submit (the Send button stays disabled during loading).
            logger.info("Waiting 10s for site to process pasted text...")
            time.sleep(10)

            if not _click_submit(page):
                logger.error(
                    "Could not find submit button on %s — skipping. "
                    "Update _SUBMIT_BUTTON_SELECTORS after inspecting the live page.",
                    job.url,
                )
                continue

            _log_page_debug_facts(page, "before-wait-success-post-click")
            success = _wait_for_success(page)
            if success:
                draft.status = "submitted"
                draft.submitted_at = datetime.now(timezone.utc)
                tracker.record_application(draft)
                logger.info("Successfully submitted: %s @ %s", job.title, job.company.name)
                _emit(f"[{idx}/{len(drafts)}] ✓ Submitted to {job.company.name}")
            else:
                logger.error(
                    "Could not confirm submission to %s — NOT recording as submitted. "
                    "Check the page manually and resubmit if needed.",
                    job.url,
                )

        except Exception as exc:
            logger.error("Error submitting to %s: %s", job.url, exc)
            _emit(f"[{idx}/{len(drafts)}] ✗ Error submitting to {job.company.name}: {exc}")
        finally:
            logger.info("Closing page for job url=%s", job.url)
            page.close()

        if delay_seconds > 0:
            logger.info("Waiting %ds before next submission…", delay_seconds)
            time.sleep(delay_seconds)