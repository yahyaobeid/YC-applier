from datetime import datetime
from pydantic import BaseModel


class Company(BaseModel):
    id: str
    name: str
    batch: str
    description: str
    industry: str
    website: str | None = None


class Job(BaseModel):
    id: str
    url: str
    title: str
    company: Company
    role_type: str
    description: str
    requirements: str
    location: str
    remote: bool
    scraped_at: datetime


class ApplicationDraft(BaseModel):
    job: Job
    match_score: int
    match_reasoning: str
    draft_paragraph: str
    status: str  # "pending_review" | "approved" | "auto_approved" | "rejected" | "submitted"
    submitted_at: datetime | None = None
