"""Dashboard stats endpoints."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from fastapi import APIRouter

from api.state import pipeline_state

router = APIRouter()

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


def _load_settings() -> dict:
    with _SETTINGS_PATH.open() as f:
        return yaml.safe_load(f)


def _load_applications() -> list[dict]:
    cfg = _load_settings()
    log_path = _PROJECT_ROOT / cfg["paths"]["applied_log"]
    if not log_path.exists():
        return []
    with log_path.open() as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


@router.get("/stats")
def get_stats():
    apps = _load_applications()
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    this_week = []
    for a in apps:
        ts = a.get("submitted_at")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                if dt >= week_ago:
                    this_week.append(a)
            except ValueError:
                pass

    status_counts: dict[str, int] = {}
    for a in apps:
        s = a.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    with pipeline_state._lock:
        pending = sum(1 for d in pipeline_state.drafts if d.get("status") == "pending")

    return {
        "total_applications": len(apps),
        "submitted": status_counts.get("submitted", 0),
        "pending_review": pending,
        "this_week": len(this_week),
        "status_breakdown": status_counts,
    }


@router.get("/applications/recent")
def get_recent_applications(limit: int = 10):
    apps = _load_applications()
    sorted_apps = sorted(apps, key=lambda a: a.get("submitted_at", ""), reverse=True)
    return sorted_apps[:limit]
