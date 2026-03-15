import asyncio
import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from yc_applier.ai.prompts import MATCHING_SYSTEM, MATCHING_USER
from yc_applier.scraper.models import Job

logger = logging.getLogger(__name__)

_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_OPENAI_MODEL = "gpt-4o-mini"
_MAX_TOKENS = 300
_CONCURRENCY = 5


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _score_job(
    client,
    job: Job,
    resume_text: str,
    sem: asyncio.Semaphore,
    provider: str,
) -> tuple[Job, int, str]:
    user_prompt = MATCHING_USER.format(
        resume_text=resume_text,
        job_title=job.title,
        company_name=job.company.name,
        role_type=job.role_type,
        location=job.location,
        remote=job.remote,
        job_description=job.description,
        job_requirements=job.requirements,
    )

    async with sem:
        if provider == "openai":
            response = await client.chat.completions.create(
                model=_OPENAI_MODEL,
                max_tokens=_MAX_TOKENS,
                temperature=0,
                messages=[
                    {"role": "system", "content": MATCHING_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = response.choices[0].message.content.strip()
        else:
            response = await client.messages.create(
                model=_ANTHROPIC_MODEL,
                max_tokens=_MAX_TOKENS,
                temperature=0,
                system=MATCHING_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
        score = int(data["score"])
        reasoning = str(data["reasoning"])
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Failed to parse matcher response for %s: %s\nRaw: %s", job.id, exc, raw)
        score = 0
        reasoning = "Parse error — could not score this job."

    return job, score, reasoning


async def score_jobs(
    jobs: list[Job],
    resume_text: str,
    min_score: int,
    api_key: str,
    provider: str = "anthropic",
) -> list[tuple[Job, int, str]]:
    """Score all jobs concurrently and return those meeting min_score."""
    if provider == "openai":
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
    else:
        client = anthropic.AsyncAnthropic(api_key=api_key)
    sem = asyncio.Semaphore(_CONCURRENCY)

    tasks = [_score_job(client, job, resume_text, sem, provider) for job in jobs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scored = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Scoring task failed: %s", result)
            continue
        job, score, reasoning = result
        if score >= min_score:
            scored.append((job, score, reasoning))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
