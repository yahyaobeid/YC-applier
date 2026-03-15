import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from yc_applier.ai.prompts import DRAFTING_SYSTEM, DRAFTING_USER
from yc_applier.scraper.models import ApplicationDraft, Job

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 250


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _draft_paragraph(
    client: anthropic.Anthropic,
    job: Job,
    resume_text: str,
) -> str:
    user_prompt = DRAFTING_USER.format(
        resume_text=resume_text,
        job_title=job.title,
        company_name=job.company.name,
        company_description=job.company.description,
        job_description=job.description,
    )

    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0.7,
        system=DRAFTING_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text.strip()


def draft_applications(
    scored_jobs: list[tuple[Job, int, str]],
    resume_text: str,
    api_key: str,
) -> list[ApplicationDraft]:
    """Generate an ApplicationDraft for each (job, score, reasoning) tuple."""
    client = anthropic.Anthropic(api_key=api_key)
    drafts = []

    for job, score, reasoning in scored_jobs:
        try:
            paragraph = _draft_paragraph(client, job, resume_text)
        except Exception as exc:
            logger.error("Failed to draft for %s (%s): %s", job.title, job.id, exc)
            paragraph = ""

        drafts.append(
            ApplicationDraft(
                job=job,
                match_score=score,
                match_reasoning=reasoning,
                draft_paragraph=paragraph,
                status="pending_review",
            )
        )

    return drafts
