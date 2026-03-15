"""Tests for api/routes/config.py."""

import yaml
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open

from api.main import app

client = TestClient(app)

_SETTINGS = {
    "filters": {"roles": ["Backend", "Full Stack"], "remote_only": True, "excluded_industries": []},
    "matching": {"min_match_score": 70, "max_jobs_per_run": 30},
    "behavior": {
        "review_mode": True,
        "auto_apply_above_score": 90,
        "application_delay_seconds": 30,
    },
    "paths": {"resume": "resume/resume.pdf", "applied_log": "data/applied_jobs.json"},
}


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------

def test_get_config_returns_yaml_contents():
    with patch("builtins.open", mock_open(read_data=yaml.dump(_SETTINGS))):
        r = client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert data["matching"]["min_match_score"] == 70
    assert data["filters"]["remote_only"] is True
    assert "paths" in data


def test_get_config_structure():
    with patch("builtins.open", mock_open(read_data=yaml.dump(_SETTINGS))):
        r = client.get("/api/config")
    data = r.json()
    assert set(data.keys()) >= {"filters", "matching", "behavior", "paths"}


# ---------------------------------------------------------------------------
# PUT /api/config
# ---------------------------------------------------------------------------

def test_update_config_returns_ok(tmp_path):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(_SETTINGS))
    new_config = {**_SETTINGS, "matching": {**_SETTINGS["matching"], "min_match_score": 80}}

    with patch("api.routes.config._SETTINGS_PATH", config_path):
        r = client.put("/api/config", json=new_config)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_update_config_persists_to_disk(tmp_path):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(_SETTINGS))
    new_config = {**_SETTINGS, "matching": {**_SETTINGS["matching"], "min_match_score": 80}}

    with patch("api.routes.config._SETTINGS_PATH", config_path):
        client.put("/api/config", json=new_config)

    saved = yaml.safe_load(config_path.read_text())
    assert saved["matching"]["min_match_score"] == 80


def test_update_config_partial_overwrite(tmp_path):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(_SETTINGS))
    new_config = {**_SETTINGS, "filters": {"roles": ["ML"], "remote_only": False}}

    with patch("api.routes.config._SETTINGS_PATH", config_path):
        client.put("/api/config", json=new_config)

    saved = yaml.safe_load(config_path.read_text())
    assert saved["filters"]["roles"] == ["ML"]
    assert saved["filters"]["remote_only"] is False
    assert saved["matching"]["min_match_score"] == 70  # unchanged


def test_update_config_roundtrip(tmp_path):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(_SETTINGS))

    with patch("api.routes.config._SETTINGS_PATH", config_path):
        client.put("/api/config", json=_SETTINGS)
        r = client.get("/api/config")

    assert r.status_code == 200
    assert r.json()["matching"]["min_match_score"] == _SETTINGS["matching"]["min_match_score"]
