"""
Unit tests for Phase 1 — Story, Script & Character Design.

Covers:
  - Pydantic schema validation (valid + invalid cases)
  - Tool functions (story_tools, character_tools, script_tools)
  - Serializer helper functions
  - LangGraph node routing logic (with mocked LLM)
  - Pipeline entry-point guard clauses
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# ── Schemas ────────────────────────────────────────────────────────────────
from shared.schemas.story_schema import Scene, StoryOutput
from shared.schemas.character_schema import (
    AppearanceDescription,
    Character,
    CharacterRoster,
    VoiceConfig,
)
from shared.schemas.script_schema import DialogueLine, SceneScript, ScriptOutput
from shared.schemas.handoff_schema import Phase2AudioHandoff, Phase3VideoHandoff
from shared.schemas.pipeline_state import Phase1State

# ── Tools ──────────────────────────────────────────────────────────────────
from agents.story_agent.tools.story_tools import estimate_duration, validate_story_arc
from agents.story_agent.tools.character_tools import check_consistency
from agents.story_agent.tools.script_tools import (
    analyze_emotions,
    build_visual_prompt,
    validate_duration,
)

# ── Serializer ─────────────────────────────────────────────────────────────
from agents.story_agent.serializer import (
    build_phase2_handoff,
    build_phase3_handoff,
    serialize_phase1_outputs,
)

# ── Graph routing ──────────────────────────────────────────────────────────
from agents.story_agent.agent import _route_character, _route_story
from langgraph.graph import END


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_story() -> Dict[str, Any]:
    return {
        "title": "The Martian Ocean",
        "genre": "sci-fi",
        "themes": ["discovery", "courage"],
        "arc": ["intro", "rising_action", "climax", "resolution"],
        "scenes": [
            {
                "scene_id": "scene_001",
                "title": "Arrival",
                "setting": "Mars surface",
                "tone": "mysterious",
                "arc_position": "intro",
                "summary": "The astronaut lands.",
                "estimated_duration_seconds": 30,
                "themes": ["discovery"],
            },
            {
                "scene_id": "scene_002",
                "title": "Discovery",
                "setting": "Underground cavern",
                "tone": "excited",
                "arc_position": "rising_action",
                "summary": "An ocean is found.",
                "estimated_duration_seconds": 40,
                "themes": ["courage"],
            },
            {
                "scene_id": "scene_003",
                "title": "Revelation",
                "setting": "Cavern shore",
                "tone": "epic",
                "arc_position": "climax",
                "summary": "First contact.",
                "estimated_duration_seconds": 45,
                "themes": ["discovery", "courage"],
            },
            {
                "scene_id": "scene_004",
                "title": "Return",
                "setting": "Mars surface",
                "tone": "peaceful",
                "arc_position": "resolution",
                "summary": "The astronaut reports home.",
                "estimated_duration_seconds": 25,
                "themes": ["discovery"],
            },
        ],
        "total_estimated_duration_seconds": 140,
        "premise": "An astronaut discovers alien life under Mars.",
        "setting_description": "Near-future Mars, dusty red surface and hidden subterranean ocean.",
    }


@pytest.fixture
def sample_roster() -> Dict[str, Any]:
    return {
        "characters": [
            {
                "character_id": "char_001",
                "name": "Zara",
                "role": "protagonist",
                "voice_config": {
                    "gender": "female",
                    "age_range": "young_adult",
                    "tone": "determined",
                    "speed": 1.0,
                    "emotion_baseline": "calm",
                    "accent": "american",
                    "tts_style_tags": ["clear", "confident"],
                },
                "appearance": {
                    "physical_description": "Tall, athletic, short black hair",
                    "clothing": "White NASA spacesuit",
                    "distinctive_features": "Red stripe on helmet",
                    "color_palette": ["white", "red", "black"],
                    "art_style_prompt": "female astronaut, short black hair, white spacesuit with red stripe",
                },
                "personality_traits": ["brave", "curious", "methodical"],
                "scenes_appearing_in": ["scene_001", "scene_002", "scene_003", "scene_004"],
                "background": "NASA's top geologist sent on first solo Mars mission.",
            }
        ],
        "global_art_style": "Studio Ghibli-style watercolour animation",
    }


@pytest.fixture
def sample_script() -> Dict[str, Any]:
    return {
        "scenes": [
            {
                "scene_id": "scene_001",
                "dialogue": [
                    {
                        "line_id": "line_001",
                        "character_id": "char_001",
                        "text": "Mars. Finally.",
                        "emotion": "calm",
                        "timing_offset_seconds": 2.0,
                        "duration_hint_seconds": 2.0,
                    }
                ],
                "visual_prompt": "Studio Ghibli watercolour, Mars dusty surface at sunset",
                "negative_visual_prompt": "blurry, watermark",
                "camera_movement": "pan_left",
                "transition_in": "fade_in",
                "transition_out": "dissolve",
                "background_music_mood": "mysterious",
                "subtitle_text": "Sol 1",
                "estimated_duration_seconds": 30,
            }
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# Schema Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestStorySchema:
    def test_valid_story_output(self, sample_story):
        story = StoryOutput(**sample_story)
        assert story.title == "The Martian Ocean"
        assert len(story.scenes) == 4

    def test_scene_duration_bounds(self):
        with pytest.raises(ValidationError):
            Scene(
                scene_id="s1",
                title="T",
                setting="S",
                tone="calm",
                arc_position="intro",
                summary="X",
                estimated_duration_seconds=5,  # below minimum of 10
                themes=[],
            )

    def test_invalid_arc_position(self):
        with pytest.raises(ValidationError):
            Scene(
                scene_id="s1",
                title="T",
                setting="S",
                tone="calm",
                arc_position="not_a_valid_position",
                summary="X",
                estimated_duration_seconds=20,
                themes=[],
            )


class TestCharacterSchema:
    def test_valid_voice_config(self):
        vc = VoiceConfig(
            gender="female",
            age_range="adult",
            tone="warm",
            speed=1.0,
            emotion_baseline="calm",
            accent="british",
            tts_style_tags=["soft"],
        )
        assert vc.speed == 1.0

    def test_speed_out_of_range(self):
        with pytest.raises(ValidationError):
            VoiceConfig(
                gender="male",
                age_range="adult",
                tone="deep",
                speed=3.0,  # above max of 2.0
                emotion_baseline="neutral",
                accent="neutral",
            )

    def test_valid_roster(self, sample_roster):
        roster = CharacterRoster(**sample_roster)
        assert len(roster.characters) == 1
        assert roster.global_art_style != ""


class TestScriptSchema:
    def test_valid_script(self, sample_script):
        script = ScriptOutput(**sample_script)
        assert len(script.scenes) == 1
        assert script.scenes[0].dialogue[0].text == "Mars. Finally."

    def test_invalid_camera_movement(self, sample_script):
        bad = dict(sample_script)
        bad["scenes"][0] = dict(sample_script["scenes"][0], camera_movement="spin")
        with pytest.raises(ValidationError):
            ScriptOutput(**bad)

    def test_dialogue_line_duration_positive(self):
        with pytest.raises(ValidationError):
            DialogueLine(
                line_id="l1",
                character_id="char_001",
                text="Hello",
                emotion="calm",
                timing_offset_seconds=0.0,
                duration_hint_seconds=0.1,  # below minimum 0.5
            )


# ═══════════════════════════════════════════════════════════════════════════
# Tool Tests — story_tools
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateStoryArc:
    def test_valid_full_arc(self):
        result = validate_story_arc.invoke(
            {"arc_positions": ["intro", "rising_action", "climax", "falling_action", "resolution"]}
        )
        assert result["is_valid"] is True
        assert result["issues"] == []

    def test_missing_climax(self):
        result = validate_story_arc.invoke(
            {"arc_positions": ["intro", "rising_action", "resolution"]}
        )
        # climax is required
        assert result["is_valid"] is False
        assert any("climax" in i for i in result["issues"])

    def test_wrong_order(self):
        result = validate_story_arc.invoke(
            {"arc_positions": ["climax", "intro", "resolution"]}
        )
        assert result["is_valid"] is False

    def test_invalid_position_name(self):
        result = validate_story_arc.invoke(
            {"arc_positions": ["intro", "drama", "climax", "resolution"]}
        )
        assert result["is_valid"] is False


class TestEstimateDuration:
    def test_reasonable_estimate(self):
        result = estimate_duration.invoke(
            {"scene_count": 5, "avg_dialogue_lines_per_scene": 3, "avg_words_per_line": 15}
        )
        assert result["estimated_total_seconds"] > 0
        assert result["avg_seconds_per_scene"] > 0

    def test_single_scene(self):
        result = estimate_duration.invoke(
            {"scene_count": 1, "avg_dialogue_lines_per_scene": 2}
        )
        assert result["estimated_total_minutes"] < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Tool Tests — character_tools
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckConsistency:
    def test_fully_consistent(self):
        result = check_consistency.invoke(
            {
                "character_ids": ["char_001", "char_002"],
                "scene_character_map": {
                    "scene_001": ["char_001", "char_002"],
                    "scene_002": ["char_001"],
                    "scene_003": ["char_001", "char_002"],
                },
            }
        )
        assert result["is_consistent"] is True

    def test_undefined_character_in_scene(self):
        result = check_consistency.invoke(
            {
                "character_ids": ["char_001"],
                "scene_character_map": {"scene_001": ["char_001", "char_999"]},
            }
        )
        assert result["is_consistent"] is False
        assert any("char_999" in i for i in result["issues"])

    def test_character_never_used(self):
        result = check_consistency.invoke(
            {
                "character_ids": ["char_001", "char_002"],
                "scene_character_map": {"scene_001": ["char_001"]},
            }
        )
        assert result["is_consistent"] is False
        assert any("char_002" in i for i in result["issues"])


# ═══════════════════════════════════════════════════════════════════════════
# Tool Tests — script_tools
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildVisualPrompt:
    def test_returns_non_empty_prompt(self):
        result = build_visual_prompt.invoke(
            {
                "scene_setting": "Mars dusty surface",
                "scene_tone": "mysterious",
                "characters_present": ["Zara"],
                "character_descriptions": ["female astronaut in white spacesuit"],
                "art_style": "Studio Ghibli watercolour",
            }
        )
        assert len(result["visual_prompt"]) > 30
        assert "Studio Ghibli" in result["visual_prompt"]
        assert result["negative_prompt"] != ""

    def test_tone_lighting_applied(self):
        result = build_visual_prompt.invoke(
            {
                "scene_setting": "underwater cave",
                "scene_tone": "tense",
                "characters_present": [],
                "character_descriptions": [],
            }
        )
        assert "shadow" in result["lighting_note"].lower() or "contrast" in result["lighting_note"].lower()


class TestValidateDuration:
    def test_short_dialogue_fits(self):
        result = validate_duration.invoke(
            {"dialogue_lines": ["Hello.", "I see it now."], "target_duration_seconds": 30}
        )
        assert result["fits"] is True

    def test_long_dialogue_exceeds(self):
        long_line = "This is a very long piece of dialogue that will certainly exceed any reasonable target. " * 5
        result = validate_duration.invoke(
            {"dialogue_lines": [long_line] * 3, "target_duration_seconds": 5}
        )
        assert result["fits"] is False
        assert "exceeds" in result["suggestion"].lower()


class TestAnalyzeEmotions:
    def test_excited_keywords(self):
        result = analyze_emotions.invoke(
            {
                "dialogue_text": "This is absolutely amazing and wonderful!",
                "scene_tone": "excited",
                "character_role": "protagonist",
            }
        )
        assert result["suggested_emotion"] == "excited"

    def test_falls_back_to_scene_tone(self):
        result = analyze_emotions.invoke(
            {
                "dialogue_text": "...",
                "scene_tone": "tense",
                "character_role": "supporting",
            }
        )
        assert result["suggested_emotion"] == "fearful"
        assert result["confidence"] == "inferred_from_scene_tone"

    def test_sad_keywords(self):
        result = analyze_emotions.invoke(
            {
                "dialogue_text": "I miss you so much, goodbye.",
                "scene_tone": "sad",
                "character_role": "protagonist",
            }
        )
        assert result["suggested_emotion"] == "sad"


# ═══════════════════════════════════════════════════════════════════════════
# Serializer Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildPhase2Handoff:
    def test_segment_count_matches_dialogue_lines(
        self, sample_story, sample_roster, sample_script
    ):
        result = build_phase2_handoff(sample_story, sample_roster, sample_script)
        total_lines = sum(len(s["dialogue"]) for s in sample_script["scenes"])
        assert result["total_segments"] == total_lines

    def test_voice_configs_keyed_by_character_id(
        self, sample_story, sample_roster, sample_script
    ):
        result = build_phase2_handoff(sample_story, sample_roster, sample_script)
        assert "char_001" in result["voice_configs"]

    def test_music_moods_keyed_by_scene_id(
        self, sample_story, sample_roster, sample_script
    ):
        result = build_phase2_handoff(sample_story, sample_roster, sample_script)
        assert "scene_001" in result["music_moods"]
        assert result["music_moods"]["scene_001"] == "mysterious"


class TestBuildPhase3Handoff:
    def test_scene_count_matches(self, sample_story, sample_roster, sample_script):
        result = build_phase3_handoff(sample_story, sample_roster, sample_script)
        assert len(result["scenes"]) == len(sample_script["scenes"])

    def test_global_art_style_propagated(self, sample_story, sample_roster, sample_script):
        result = build_phase3_handoff(sample_story, sample_roster, sample_script)
        assert "Ghibli" in result["global_art_style"]

    def test_character_appearance_prompts(self, sample_story, sample_roster, sample_script):
        result = build_phase3_handoff(sample_story, sample_roster, sample_script)
        assert "char_001" in result["character_appearance_prompts"]


class TestSerializePhase1Outputs:
    def test_all_artifacts_written(self, sample_story, sample_roster, sample_script, tmp_path):
        paths = serialize_phase1_outputs(
            story=sample_story,
            roster=sample_roster,
            script=sample_script,
            tools_log=[],
            errors=[],
            run_status="success",
            output_dir=tmp_path,
        )
        expected_keys = {
            "story",
            "characters",
            "script",
            "phase2_audio_handoff",
            "phase3_video_handoff",
            "summary",
        }
        assert expected_keys == set(paths.keys())
        for path in paths.values():
            assert Path(path).exists()

    def test_summary_contains_stats(self, sample_story, sample_roster, sample_script, tmp_path):
        paths = serialize_phase1_outputs(
            story=sample_story,
            roster=sample_roster,
            script=sample_script,
            tools_log=[{"node": "story_agent", "tool": "validate_story_arc", "args": {}}],
            errors=[],
            run_status="success",
            output_dir=tmp_path,
        )
        with open(paths["summary"], encoding="utf-8") as fh:
            summary = json.load(fh)
        assert summary["run_status"] == "success"
        assert summary["stats"]["scene_count"] == 4
        assert len(summary["tools_log"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Graph Routing Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphRouting:
    def _base_state(self) -> Phase1State:
        return {
            "user_prompt": "test",
            "story_output": None,
            "character_roster": None,
            "script_output": None,
            "errors": [],
            "tools_log": [],
            "retry_counts": {},
        }

    def test_route_story_to_character_when_success(self):
        state = self._base_state()
        state["story_output"] = {"title": "T", "scenes": []}
        assert _route_story(state) == "character_agent"

    def test_route_story_to_end_on_failure(self):
        state = self._base_state()
        state["story_output"] = None
        assert _route_story(state) == END

    def test_route_character_to_script_when_success(self):
        state = self._base_state()
        state["character_roster"] = {"characters": []}
        assert _route_character(state) == "script_agent"

    def test_route_character_to_end_on_failure(self):
        state = self._base_state()
        state["character_roster"] = None
        assert _route_character(state) == END


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Guard Tests (no LLM calls needed)
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineGuards:
    def test_empty_prompt_returns_error(self):
        from agents.story_agent.planner import run_phase1
        result = run_phase1("")
        assert result["success"] is False
        assert any("empty" in e.lower() for e in result["errors"])

    def test_missing_api_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from agents.story_agent.planner import run_phase1
        result = run_phase1("A brave knight")
        assert result["success"] is False
        assert any("GOOGLE_API_KEY" in e for e in result["errors"])
