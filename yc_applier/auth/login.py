import logging
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://account.ycombinator.com/?continue=https%3A%2F%2Fwww.workatastartup.com%2F"
_HOME_URL = "https://www.workatastartup.com/"
_SESSION_FILE = "auth.json"


def _session_path(session_dir: Path) -> Path:
    return session_dir / _SESSION_FILE


def _is_logged_in(page: Page) -> bool:
    """Check for a login indicator present when authenticated."""
    try:
        # The nav shows a user avatar / account link when logged in
        page.wait_for_selector("a[href*='/account'], [data-testid='user-menu']", timeout=5_000)
        return True
    except Exception:
        return False


def _do_login(page: Page, email: str, password: str) -> None:
    logger.info("Logging in as %s …", email)
    page.goto(_LOGIN_URL, wait_until="networkidle")

    page.fill("input[name='username'], input[id='ycid-input']", email)
    page.fill("input[type='password'], input[name='password']", password)
    page.click("button[type='submit']")

    # Wait for redirect back to workatastartup.com
    page.wait_for_url("*workatastartup.com*", timeout=20_000)
    page.wait_for_load_state("networkidle")

    if not _is_logged_in(page):
        raise RuntimeError(
            "Login appeared to complete but could not confirm authenticated state. "
            "Check YC_EMAIL / YC_PASSWORD and try again."
        )
    logger.info("Login successful.")


def get_authenticated_context(
    playwright: Playwright,
    email: str,
    password: str,
    session_dir: Path,
    headless: bool = True,
) -> BrowserContext:
    """Return a Playwright BrowserContext with a valid authenticated session.

    If a saved session exists it is reused; otherwise a fresh login is performed
    and the session is persisted to *session_dir* for future runs.
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = _session_path(session_dir)

    browser = playwright.chromium.launch(headless=headless)

    # --- Try saved session first ---
    if session_file.exists():
        logger.info("Loading saved browser session from %s", session_file)
        context = browser.new_context(storage_state=str(session_file))
        page = context.new_page()
        page.goto(_HOME_URL, wait_until="networkidle")

        if _is_logged_in(page):
            logger.info("Saved session is still valid.")
            page.close()
            return context

        logger.warning("Saved session expired — re-logging in.")
        page.close()
        context.close()

    # --- Fresh login ---
    context = browser.new_context()
    page = context.new_page()
    _do_login(page, email, password)
    page.close()

    context.storage_state(path=str(session_file))
    logger.info("Session saved to %s", session_file)
    return context


def clear_session(session_dir: Path) -> None:
    """Delete saved auth state so the next run forces a fresh login."""
    session_file = _session_path(session_dir)
    if session_file.exists():
        session_file.unlink()
        logger.info("Deleted saved session: %s", session_file)
    else:
        logger.info("No saved session found at %s", session_file)
