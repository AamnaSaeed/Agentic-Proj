from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class JsonStateStorage:
    """Small JSON file storage used by the Phase 4 job system."""

    def read(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return payload
