# YC-Applier

AI agent that automates job applications on [workatastartup.com](https://www.workatastartup.com).

## What it does

1. **Scrapes** matching jobs (Full Stack / Backend / ML) via Algolia API interception
2. **Scores** each job against your resume using Claude Haiku (fast, cheap)
3. **Drafts** a personalised application paragraph using Claude Sonnet (quality)
4. **Reviews** drafts interactively — or auto-submits above a confidence threshold
5. **Submits** the application form via Playwright and logs every attempt

---

## Quick start

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Install Playwright browser
playwright install chromium

# 3. Configure credentials
cp .env.example .env
# edit .env — set YC_EMAIL, YC_PASSWORD, ANTHROPIC_API_KEY

# 4. Drop your resume
cp ~/Downloads/resume.pdf resume/resume.pdf

# 5. Dry run (no submission)
yc-apply run --dry-run

# 6. Full run with interactive review
yc-apply run
```

---

## CLI commands

| Command | Description |
|---|---|
| `yc-apply run` | Full pipeline |
| `yc-apply run --dry-run` | Scrape + score + draft, skip submission |
| `yc-apply run --no-review` | Auto-apply above score threshold only |
| `yc-apply list-applied` | Show audit log as a table |
| `yc-apply clear-session` | Force fresh browser login |

---

## Configuration

Edit `config/settings.yaml`:

```yaml
filters:
  roles: ["Full Stack", "Backend", "ML"]
  remote_only: true

matching:
  min_match_score: 70        # skip below this
  max_jobs_per_run: 30

behavior:
  review_mode: true
  auto_apply_above_score: 90  # skip review prompt for these
  application_delay_seconds: 30
```

---

## ⚠️ Before submitting real applications

The form selectors in `yc_applier/application/submitter.py` are best-guess approximations.

1. Log into workatastartup.com in a browser
2. Navigate to a job listing and open DevTools
3. Inspect the application textarea and submit button
4. Update `_TEXTAREA_SELECTORS` and `_SUBMIT_BUTTON_SELECTORS` in `submitter.py`

Same applies to the Algolia filter selectors in `scraper/jobs.py` — verify with live network inspection.

---

## Running tests

```bash
pytest tests/
```
