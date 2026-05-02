from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class DialogueLine(BaseModel):
    line_id: str = Field(description="Unique identifier, e.g. 'line_001'")
    character_id: str = Field(description="References character_id from CharacterRoster")
    text: str = Field(description="Spoken dialogue or narration text")
    emotion: str = Field(description="Emotion for TTS: excited, sad, angry, calm, curious, etc.")
    timing_offset_seconds: float = Field(ge=0.0, description="Seconds from scene start when this line begins")
    duration_hint_seconds: float = Field(ge=0.5, description="Estimated time in seconds to speak this line")


class SceneScript(BaseModel):
    scene_id: str = Field(description="Must match a scene_id from StoryOutput")
    dialogue: List[DialogueLine] = Field(description="All dialogue lines for this scene in chronological order")
    visual_prompt: str = Field(
        description="Detailed image-generation prompt for this scene (50-150 words)"
    )
    negative_visual_prompt: str = Field(
        default="blurry, low quality, distorted faces, watermark, text overlay, extra limbs",
        description="Elements to exclude from image generation",
    )
    camera_movement: Literal[
        "static", "zoom_in", "zoom_out", "pan_left", "pan_right", "ken_burns"
    ] = Field(default="ken_burns")
    transition_in: Literal["cut", "fade_in", "dissolve", "wipe"] = Field(default="fade_in")
    transition_out: Literal["cut", "fade_out", "dissolve", "wipe"] = Field(default="fade_out")
    background_music_mood: str = Field(
        description="Music mood keyword for BGM selection, e.g. 'epic', 'peaceful', 'tense'"
    )
    subtitle_text: str = Field(default="", description="Optional scene title-card text; empty string if none")
    estimated_duration_seconds: int = Field(ge=5, description="Estimated scene duration in seconds")


class ScriptOutput(BaseModel):
    scenes: List[SceneScript] = Field(description="Ordered script for every scene in the story")
