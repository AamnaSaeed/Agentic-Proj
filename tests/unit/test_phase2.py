from __future__ import annotations

import wave
from pathlib import Path

from agents.audio_agent.agent import run_phase2
from mcp.tools.audio_tools.tts_tool import synthesize_tts_segment


def _sample_handoff():
    voice_config = {
        "gender": "female",
        "age_range": "young_adult",
        "tone": "warm",
        "speed": 1.0,
        "emotion_baseline": "curious",
        "accent": "neutral",
        "tts_style_tags": ["clear"],
    }
    return {
        "voice_configs": {"char_001": voice_config},
        "audio_segments": [
            {
                "segment_id": "scene_001_line_001",
                "scene_id": "scene_001",
                "character_id": "char_001",
                "line_id": "line_001",
                "text": "The signal is getting stronger.",
                "voice_config": voice_config,
                "timing_offset_seconds": 0.0,
                "duration_hint_seconds": 1.0,
                "emotion": "curious",
            },
            {
                "segment_id": "scene_001_line_002",
                "scene_id": "scene_001",
                "character_id": "char_001",
                "line_id": "line_002",
                "text": "I think we found it.",
                "voice_config": voice_config,
                "timing_offset_seconds": 1.5,
                "duration_hint_seconds": 1.0,
                "emotion": "excited",
            },
        ],
        "music_moods": {"scene_001": "mysterious"},
        "total_segments": 2,
    }


def _wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def test_synthesize_tts_segment_writes_wav(tmp_path):
    segment = _sample_handoff()["audio_segments"][0]
    result = synthesize_tts_segment(segment, tmp_path)

    assert Path(result["audio_file"]).exists()
    assert result["duration_seconds"] >= 0.5
    assert _wav_duration(result["audio_file"]) > 0.9


def test_run_phase2_writes_manifest_and_audio_assets(tmp_path):
    result = run_phase2(_sample_handoff(), output_dir=tmp_path)

    assert result["success"] is True
    assert Path(result["timing_manifest"]).exists()
    assert Path(result["full_audio"]).exists()
    assert result["segment_count"] == 2
    assert result["scene_count"] == 1

    manifest = result["manifest"]
    assert manifest["total_segments"] == 2
    assert len(manifest["segments"]) == 2
    assert manifest["segments"][1]["start_ms"] == 1500
    assert manifest["segments"][1]["end_ms"] > manifest["segments"][1]["start_ms"]
    assert Path(manifest["scene_tracks"][0]["audio_file"]).exists()


def test_run_phase2_rejects_invalid_handoff(tmp_path):
    result = run_phase2({"audio_segments": []}, output_dir=tmp_path)

    assert result["success"] is False
    assert "Invalid Phase 2 handoff" in result["errors"][0]
