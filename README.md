# YC-Applier

AI agent that automates job applications on [workatastartup.com](https://www.workatastartup.com).

## What it does

1. **Scrapes** matching jobs (Full Stack / Backend / ML) via Algolia API interception
2. **Scores** each job against your resume using Claude Haiku or GPT-4o-mini (fast, cheap)
3. **Drafts** a personalised application paragraph using Claude Sonnet or GPT-4o (quality)
4. **Reviews** drafts in a web UI — approve, edit, or skip before submission
5. **Submits** the application form via Playwright and logs every attempt

---

## Quick start

### 1. Install Python dependencies

```bash
pip install -e ".[dev]"
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```
YC_EMAIL=you@example.com
YC_PASSWORD=yourpassword
ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY=sk-...
```

### 3. Drop your resume

```bash
cp ~/Downloads/resume.pdf resume/resume.pdf
```

### 4. Start the web UI

```bash
# Terminal 1 — API server
uvicorn api.main:app --reload

# Terminal 2 — Frontend dev server
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Web UI pages

| Page | Description |
|---|---|
| **Dashboard** | Stats overview, recent applications, quick-start button |
| **Pipeline** | Run the scrape → score → draft pipeline with live progress log |
| **Review** | Approve, edit, or skip generated drafts before submission |
| **Applications** | Full audit log with search and status filter |

---

## CLI commands (alternative to web UI)

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

## AI providers

Both Anthropic and OpenAI are supported. Select the provider in the web UI or set `ai_provider` in settings.

| Provider | Scoring model | Drafting model |
|---|---|---|
| `anthropic` (default) | claude-haiku-4-5 | claude-sonnet-4-6 |
| `openai` | gpt-4o-mini | gpt-4o |

---

## Running tests

```bash
pytest tests/
```

---

## Production build

```bash
cd frontend
npm run build       # outputs to frontend/dist/
# FastAPI automatically serves frontend/dist/ as static files
uvicorn api.main:app
```
