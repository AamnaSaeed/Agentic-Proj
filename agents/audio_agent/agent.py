from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

from pydantic import ValidationError

from mcp.tools.audio_tools.audio_merger import concatenate_wavs, mix_tracks
from mcp.tools.audio_tools.bgm_tool import generate_bgm_track
from mcp.tools.audio_tools.tts_tool import synthesize_tts_segment
from shared.schemas.handoff_schema import Phase2AudioHandoff


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "outputs" / "phase2"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _load_handoff(handoff: str | Path | Dict[str, Any] | Phase2AudioHandoff) -> Phase2AudioHandoff:
    if isinstance(handoff, Phase2AudioHandoff):
        return handoff
    if isinstance(handoff, (str, Path)):
        with Path(handoff).open(encoding="utf-8") as fh:
            return Phase2AudioHandoff.model_validate(json.load(fh))
    return Phase2AudioHandoff.model_validate(handoff)


def _scene_ids(segments: Iterable[Dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for segment in segments:
        scene_id = segment["scene_id"]
        if scene_id not in ordered:
            ordered.append(scene_id)
    return ordered


def run_phase2(
    handoff: str | Path | Dict[str, Any] | Phase2AudioHandoff,
    output_dir: str | Path | None = None,
    include_bgm: bool = True,
) -> Dict[str, Any]:
    """Run Phase 2 audio generation from a Phase 1 audio handoff.

    The default implementation is fully offline and deterministic. It creates
    one WAV per dialogue segment, one optional BGM pad per scene, scene mixes,
    a combined audio track, and a timing manifest for Phase 3.
    """
    try:
        audio_handoff = _load_handoff(handoff)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return {"success": False, "errors": [f"Invalid Phase 2 handoff: {exc}"]}

    configured_output_root = Path(os.environ.get("PHASE2_OUTPUT_DIR", DEFAULT_OUTPUT_ROOT))
    run_dir = Path(output_dir) if output_dir else configured_output_root / _timestamp()
    segments_dir = run_dir / "segments"
    bgm_dir = run_dir / "bgm"
    scenes_dir = run_dir / "scenes"

    segment_outputs: list[Dict[str, Any]] = []
    manifest_segments: list[Dict[str, Any]] = []
    raw_segments = [segment.model_dump() for segment in audio_handoff.audio_segments]

    for segment in raw_segments:
        tts_output = synthesize_tts_segment(segment, segments_dir)
        start_ms = int(float(segment["timing_offset_seconds"]) * 1000)
        duration_ms = int(float(tts_output["duration_seconds"]) * 1000)
        end_ms = start_ms + duration_ms

        segment_record = {
            "segment_id": segment["segment_id"],
            "scene_id": segment["scene_id"],
            "character_id": segment["character_id"],
            "line_id": segment["line_id"],
            "text": segment["text"],
            "emotion": segment["emotion"],
            "audio_file": tts_output["audio_file"],
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": duration_ms,
            "provider": tts_output["provider"],
        }
        segment_outputs.append(segment_record)
        manifest_segments.append(segment_record)

    scene_tracks: list[Dict[str, Any]] = []
    bgm_tracks: list[Dict[str, Any]] = []
    for scene_id in _scene_ids(raw_segments):
        scene_segments = [item for item in segment_outputs if item["scene_id"] == scene_id]
        scene_duration = max((item["end_ms"] for item in scene_segments), default=1000) / 1000.0 + 0.5
        tracks: list[Dict[str, Any]] = [
            {"audio_file": item["audio_file"], "start_seconds": item["start_ms"] / 1000.0}
            for item in scene_segments
        ]

        if include_bgm:
            bgm = generate_bgm_track(
                scene_id=scene_id,
                mood=audio_handoff.music_moods.get(scene_id, "neutral"),
                duration_seconds=scene_duration,
                output_dir=bgm_dir,
            )
            bgm_tracks.append(bgm)
            tracks.insert(0, {"audio_file": bgm["audio_file"], "start_seconds": 0.0})

        scene_mix = mix_tracks(
            tracks=tracks,
            output_path=scenes_dir / f"{scene_id}_mix.wav",
            duration_seconds=scene_duration,
        )
        scene_tracks.append({"scene_id": scene_id, **scene_mix})

    full_audio = concatenate_wavs(
        [track["audio_file"] for track in scene_tracks],
        run_dir / "full_audio.wav",
    )

    manifest = {
        "phase": "phase2_audio",
        "run_status": "success",
        "output_dir": str(run_dir),
        "segments": manifest_segments,
        "scene_tracks": scene_tracks,
        "bgm_tracks": bgm_tracks,
        "full_audio": full_audio,
        "total_segments": len(manifest_segments),
        "total_duration_ms": int(float(full_audio["duration_seconds"]) * 1000),
    }
    summary = {
        "success": True,
        "output_dir": str(run_dir),
        "timing_manifest": str(run_dir / "timing_manifest.json"),
        "full_audio": full_audio["audio_file"],
        "scene_count": len(scene_tracks),
        "segment_count": len(manifest_segments),
        "providers": {
            "tts": sorted({segment["provider"] for segment in segment_outputs}),
            "bgm": "offline_procedural_bgm" if include_bgm else "disabled",
        },
    }

    _write_json(run_dir / "timing_manifest.json", manifest)
    _write_json(run_dir / "summary.json", summary)
    return {**summary, "manifest": manifest, "errors": []}


if __name__ == "__main__":
    default_handoff = (
        PROJECT_ROOT
        / "data"
        / "outputs"
        / "phase1"
        / "20260502_173240"
        / "phase2_audio_handoff.json"
    )
    handoff_path = Path(os.environ.get("PHASE2_HANDOFF_PATH", default_handoff))
    result = run_phase2(handoff_path)
    print(json.dumps({k: v for k, v in result.items() if k != "manifest"}, indent=2))
