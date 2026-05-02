"""
Handoff schemas consumed by Phase 2 (audio) and Phase 3 (video).
These are derived from the Phase 1 outputs by the serializer.
"""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field

from shared.schemas.character_schema import VoiceConfig


# ── Phase 2 (Audio) Handoff ────────────────────────────────────────────────

class AudioSegment(BaseModel):
    segment_id: str = Field(description="Unique segment key, e.g. 'scene_001_line_001'")
    scene_id: str
    character_id: str
    line_id: str
    text: str = Field(description="Text to synthesise")
    voice_config: VoiceConfig
    timing_offset_seconds: float = Field(ge=0.0)
    duration_hint_seconds: float = Field(ge=0.5)
    emotion: str


class Phase2AudioHandoff(BaseModel):
    voice_configs: Dict[str, VoiceConfig] = Field(
        description="character_id → VoiceConfig map for fast lookup by the audio agent"
    )
    audio_segments: List[AudioSegment] = Field(
        description="All audio segments ordered by scene then by timing offset"
    )
    music_moods: Dict[str, str] = Field(
        description="scene_id → BGM mood keyword map"
    )
    total_segments: int


# ── Phase 3 (Video) Handoff ────────────────────────────────────────────────

class SceneVisualSpec(BaseModel):
    scene_id: str
    visual_prompt: str
    negative_prompt: str
    camera_movement: str
    transition_in: str
    transition_out: str
    duration_seconds: int
    character_ids_in_scene: List[str]


class Phase3VideoHandoff(BaseModel):
    scenes: List[SceneVisualSpec] = Field(description="Ordered visual specification for every scene")
    character_appearance_prompts: Dict[str, str] = Field(
        description="character_id → art_style_prompt for consistent character rendering"
    )
    global_art_style: str = Field(description="Art style directive applied uniformly to all scene visuals")
