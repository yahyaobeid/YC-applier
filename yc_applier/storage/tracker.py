import json
from datetime import datetime, timezone
from pathlib import Path

from yc_applier.scraper.models import ApplicationDraft


class ApplicationTracker:
    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.log_path.exists():
            return {}
        with self.log_path.open() as f:
            try:
                data = json.load(f)
                # Keyed by job id for O(1) dedup
                return {rec["job_id"]: rec for rec in data} if isinstance(data, list) else data
            except (json.JSONDecodeError, KeyError):
                return {}

    def _save(self) -> None:
        with self.log_path.open("w") as f:
            json.dump(list(self._records.values()), f, indent=2, default=str)

    def already_applied(self, job_id: str) -> bool:
        return job_id in self._records

    def record_application(self, draft: ApplicationDraft) -> None:
        self._records[draft.job.id] = {
            "job_id": draft.job.id,
            "job_title": draft.job.title,
            "company_name": draft.job.company.name,
            "job_url": draft.job.url,
            "match_score": draft.match_score,
            "status": draft.status,
            "submitted_at": (
                draft.submitted_at.isoformat()
                if draft.submitted_at
                else datetime.now(timezone.utc).isoformat()
            ),
        }
        self._save()

    def all_records(self) -> list[dict]:
        return list(self._records.values())
