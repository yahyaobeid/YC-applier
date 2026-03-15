"""Applications audit log endpoints."""

import json
from pathlib import Path

import yaml
from fastapi import APIRouter

router = APIRouter()

_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_settings() -> dict:
    with (_PROJECT_ROOT / "config" / "settings.yaml").open() as f:
        return yaml.safe_load(f)


def _load_applications() -> list[dict]:
    cfg = _load_settings()
    log_path = _PROJECT_ROOT / cfg["paths"]["applied_log"]
    if not log_path.exists():
        return []
    with log_path.open() as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


@router.get("/applications")
def list_applications(status: str = None):
    apps = _load_applications()
    if status:
        apps = [a for a in apps if a.get("status") == status]
    return sorted(apps, key=lambda a: a.get("submitted_at", ""), reverse=True)
