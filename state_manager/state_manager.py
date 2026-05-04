from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from state_manager.storage import JsonStateStorage


class StateManager:
    """Thin facade around JSON state persistence."""

    def __init__(self, storage: JsonStateStorage | None = None):
        self.storage = storage or JsonStateStorage()

    def load(self, path: Path) -> Optional[Dict[str, Any]]:
        return self.storage.read(path)

    def save(self, path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.storage.write(path, payload)
