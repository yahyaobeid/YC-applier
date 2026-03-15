"""Draft review endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import pipeline_state

router = APIRouter()


@router.get("")
def list_drafts():
    with pipeline_state._lock:
        return [dict(d) for d in pipeline_state.drafts]


@router.post("/{draft_id}/approve")
def approve_draft(draft_id: str):
    if not pipeline_state.update_draft(draft_id, status="approved"):
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"status": "approved"}


class EditRequest(BaseModel):
    draft_paragraph: str


@router.post("/{draft_id}/edit")
def edit_draft(draft_id: str, body: EditRequest):
    if not pipeline_state.update_draft(
        draft_id, draft_paragraph=body.draft_paragraph, status="approved"
    ):
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"status": "edited"}


@router.post("/{draft_id}/skip")
def skip_draft(draft_id: str):
    if not pipeline_state.update_draft(draft_id, status="skipped"):
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"status": "skipped"}
