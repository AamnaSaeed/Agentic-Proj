"""
subtitle_tool.py — SRT Subtitle Generator (Phase 3)

Converts the Phase 2 timing_manifest.json into an SRT subtitle file
that can be burned into the video.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from mcp.base_tool import BaseTool


def ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp: HH:MM:SS,mmm"""
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(timing_manifest: List[Dict], output_path: str) -> str:
    """
    timing_manifest entries expected shape:
      { scene_id, audio_file, start_ms, end_ms, text?, character? }
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    lines = []
    idx = 1
    for entry in timing_manifest:
        start_ms = int(entry.get("start_ms", 0))
        end_ms = int(entry.get("end_ms", start_ms + 2000))
        text = entry.get("text", entry.get("dialogue", "")).strip()
        character = entry.get("character", "")
        if not text:
            continue
        label = f"{character}: {text}" if character else text
        lines.append(str(idx))
        lines.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}")
        lines.append(label)
        lines.append("")
        idx += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


class SubtitleTool(BaseTool):
    name = "subtitle_tool"
    description = "Generates SRT subtitle file from timing manifest."

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_inputs(["timing_manifest", "output_path"], kwargs)
        path = build_srt(kwargs["timing_manifest"], kwargs["output_path"])
        return {"success": True, "output_path": path}