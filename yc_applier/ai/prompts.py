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
You are helping a software engineer write the body of a job application email. \
The greeting and sign-off will be added separately — write only the body.

Tone: casual-professional. Sound like a real person writing a genuine email, \
not a cover letter template. Friendly but competent.

Rules:
- Write in first person
- 3–5 sentences
- Mention 1–2 specific things from your background that are directly relevant \
  to this role — concrete details, not vague claims
- Mention something specific about the company or role that genuinely interests you
- Avoid all buzzwords and clichés: "passionate", "team player", "fast learner", \
  "I would be a great fit", "I am excited to apply", "leverage", "synergy"
- No filler sentences — every sentence should add real information
- Output plain text only — no bullet points, no markdown, no headers, no greeting, \
  no sign-off
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

Write 3–5 sentences for the body of my application email. \
Do not include a greeting or sign-off — just the body.
"""
