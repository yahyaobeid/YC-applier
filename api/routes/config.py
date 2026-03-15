"""Settings read/write endpoints."""

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter()

_SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


@router.get("/config")
def get_config():
    with _SETTINGS_PATH.open() as f:
        return yaml.safe_load(f)


@router.put("/config")
async def update_config(body: dict[str, Any]):
    try:
        with _SETTINGS_PATH.open("w") as f:
            yaml.dump(body, f, default_flow_style=False)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
