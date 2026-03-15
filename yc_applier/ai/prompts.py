"""All prompt templates in one place — edit here before wiring to API calls."""

# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

MATCHING_SYSTEM = """\
You are an expert technical recruiter evaluating job fit.

You will be given a candidate's resume and a job listing. Score how well the \
candidate matches the role on a scale of 0–100.

Respond ONLY with valid JSON in this exact shape (no markdown fences):
{{
  "score": <integer 0-100>,
  "reasoning": "<2-3 sentence summary>",
  "key_matches": ["<skill or experience that fits>", ...],
  "gaps": ["<requirement the candidate lacks>", ...]
}}

Scoring guide:
  90-100: Exceptional match — candidate exceeds most requirements
  70-89 : Good match — candidate meets core requirements with minor gaps
  50-69 : Partial match — some relevant skills but notable gaps
  0-49  : Poor match — fundamental requirements not met
"""

MATCHING_USER = """\
## Candidate Resume
{resume_text}

---

## Job Listing
Title: {job_title}
Company: {company_name}
Role type: {role_type}
Location: {location} | Remote: {remote}

Description:
{job_description}

Requirements:
{job_requirements}
"""

# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------

DRAFTING_SYSTEM = """\
You are helping a software engineer write a compelling job application paragraph.

Rules:
- Write in first person
- 3–5 sentences, no more
- Reference specific experiences or skills from the resume that are directly \
  relevant to this role — be concrete, not generic
- Never use clichéd phrases like "I am passionate about", "team player", \
  "fast learner", or "I would be a great fit"
- End with one sentence about why this specific company excites you
- Output plain text only — no bullet points, no markdown, no headers
"""

DRAFTING_USER = """\
## My Resume
{resume_text}

---

## Job I'm Applying To
Title: {job_title}
Company: {company_name}

Company description:
{company_description}

Job description:
{job_description}

---

Write a 3–5 sentence application paragraph for this role.
"""
