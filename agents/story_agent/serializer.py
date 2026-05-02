"""
Phase 1 Serializer — saves all output artifacts to disk.

Artifacts produced:
  story.json              — StoryOutput
  characters.json         — CharacterRoster
  script.json             — ScriptOutput
  phase2_audio_handoff.json  — consumed by Phase 2 (audio agent)
  phase3_video_handoff.json  — consumed by Phase 3 (video agent)
  summary.json            — run metadata, tool log, artifact index
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────

def _output_dir() -> Path:
    base = os.environ.get("PHASE1_OUTPUT_DIR", "data/outputs")
    run_dir = Path(base) / "phase1" / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(data: Any, path: Path) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("Saved artifact: %s", path)
    return str(path)


# ── Handoff builders ───────────────────────────────────────────────────────

def build_phase2_handoff(
    story: Dict[str, Any],
    roster: Dict[str, Any],
    script: Dict[str, Any],
) -> Dict[str, Any]:
    """Constructs phase2_audio_handoff.json from Phase 1 outputs."""
    voice_configs: Dict[str, Any] = {
        char["character_id"]: char["voice_config"]
        for char in roster.get("characters", [])
    }

    audio_segments: List[Dict[str, Any]] = []
    for scene_script in script.get("scenes", []):
        scene_id = scene_script["scene_id"]
        for line in scene_script.get("dialogue", []):
            audio_segments.append(
                {
                    "segment_id": f"{scene_id}_{line['line_id']}",
                    "scene_id": scene_id,
                    "character_id": line["character_id"],
                    "line_id": line["line_id"],
                    "text": line["text"],
                    "voice_config": voice_configs.get(line["character_id"], {}),
                    "timing_offset_seconds": line.get("timing_offset_seconds", 0.0),
                    "duration_hint_seconds": line.get("duration_hint_seconds", 3.0),
                    "emotion": line.get("emotion", "neutral"),
                }
            )

    music_moods: Dict[str, str] = {
        s["scene_id"]: s.get("background_music_mood", "neutral")
        for s in script.get("scenes", [])
    }

    return {
        "voice_configs": voice_configs,
        "audio_segments": audio_segments,
        "music_moods": music_moods,
        "total_segments": len(audio_segments),
    }


def build_phase3_handoff(
    story: Dict[str, Any],
    roster: Dict[str, Any],
    script: Dict[str, Any],
) -> Dict[str, Any]:
    """Constructs phase3_video_handoff.json from Phase 1 outputs."""
    char_prompts: Dict[str, str] = {
        char["character_id"]: char["appearance"].get("art_style_prompt", "")
        for char in roster.get("characters", [])
    }

    # Build scene → characters map from roster
    scene_chars: Dict[str, List[str]] = {}
    for char in roster.get("characters", []):
        for sid in char.get("scenes_appearing_in", []):
            scene_chars.setdefault(sid, []).append(char["character_id"])

    # Duration lookup from story
    story_durations: Dict[str, int] = {
        s["scene_id"]: s.get("estimated_duration_seconds", 30)
        for s in story.get("scenes", [])
    }

    scene_visuals: List[Dict[str, Any]] = []
    for ss in script.get("scenes", []):
        sid = ss["scene_id"]
        scene_visuals.append(
            {
                "scene_id": sid,
                "visual_prompt": ss.get("visual_prompt", ""),
                "negative_prompt": ss.get(
                    "negative_visual_prompt",
                    "blurry, low quality, distorted faces, watermark",
                ),
                "camera_movement": ss.get("camera_movement", "ken_burns"),
                "transition_in": ss.get("transition_in", "fade_in"),
                "transition_out": ss.get("transition_out", "fade_out"),
                "duration_seconds": ss.get(
                    "estimated_duration_seconds", story_durations.get(sid, 30)
                ),
                "character_ids_in_scene": scene_chars.get(sid, []),
            }
        )

    return {
        "scenes": scene_visuals,
        "character_appearance_prompts": char_prompts,
        "global_art_style": roster.get("global_art_style", "cinematic animation"),
    }


# ── Public API ─────────────────────────────────────────────────────────────

def serialize_phase1_outputs(
    story: Dict[str, Any],
    roster: Dict[str, Any],
    script: Dict[str, Any],
    tools_log: List[Dict[str, Any]],
    errors: List[str],
    run_status: str = "success",
    output_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """Saves all Phase 1 artifacts and returns a path map.

    Args:
        story:      StoryOutput dict.
        roster:     CharacterRoster dict.
        script:     ScriptOutput dict.
        tools_log:  Accumulated tool-call log from all nodes.
        errors:     Error messages from the pipeline run.
        run_status: 'success' | 'partial' | 'failed'.
        output_dir: Override output directory (uses env / default if None).

    Returns:
        Dict mapping artifact name → absolute file path string.
    """
    out = output_dir or _output_dir()
    paths: Dict[str, str] = {}

    paths["story"] = _write_json(story, out / "story.json")
    paths["characters"] = _write_json(roster, out / "characters.json")
    paths["script"] = _write_json(script, out / "script.json")

    phase2 = build_phase2_handoff(story, roster, script)
    paths["phase2_audio_handoff"] = _write_json(phase2, out / "phase2_audio_handoff.json")

    phase3 = build_phase3_handoff(story, roster, script)
    paths["phase3_video_handoff"] = _write_json(phase3, out / "phase3_video_handoff.json")

    summary = {
        "run_status": run_status,
        "timestamp": datetime.now().isoformat(),
        "errors": errors,
        "tools_log": tools_log,
        "artifact_paths": paths,
        "stats": {
            "scene_count": len(story.get("scenes", [])),
            "character_count": len(roster.get("characters", [])),
            "total_dialogue_lines": sum(
                len(s.get("dialogue", [])) for s in script.get("scenes", [])
            ),
            "estimated_total_seconds": story.get("total_estimated_duration_seconds", 0),
            "total_audio_segments": phase2["total_segments"],
        },
    }
    paths["summary"] = _write_json(summary, out / "summary.json")

    logger.info("Phase 1 artifacts saved to: %s", out)
    return paths
