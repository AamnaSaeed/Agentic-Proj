from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from state_manager.state_manager import StateManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_ROOT = PROJECT_ROOT / "data" / "jobs"


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class JobStore:
    """Tiny JSON-backed job store for Phase 4 orchestration state."""

    def __init__(self, root: Path = JOBS_ROOT):
        self.root = root
        self.state_manager = StateManager()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, prompt: str) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = utc_now()
        state = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "pending",
            "current_phase": None,
            "phases": {"1": "pending", "2": "pending", "3": "pending"},
            "progress": 0,
            "message": "Job queued",
            "errors": [],
            "outputs": {},
            "created_at": now,
            "updated_at": now,
        }
        self.save(job_id, state)
        return state

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def state_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "state.json"

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self.state_path(job_id)
        return self.state_manager.load(path)

    def save(self, job_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        state["updated_at"] = utc_now()
        path = self.state_path(job_id)
        return self.state_manager.save(path, state)

    def update(self, job_id: str, **changes: Any) -> Dict[str, Any]:
        state = self.get(job_id)
        if state is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        for key, value in changes.items():
            if key == "outputs":
                state.setdefault("outputs", {}).update(value)
            elif key == "phases":
                state.setdefault("phases", {}).update(value)
            elif key == "errors":
                state.setdefault("errors", []).extend(value)
            else:
                state[key] = value
        return self.save(job_id, state)
