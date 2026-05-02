from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class Scene(BaseModel):
    scene_id: str = Field(description="Unique scene identifier, e.g. 'scene_001'")
    title: str = Field(description="Short descriptive title for the scene")
    setting: str = Field(description="Where and when the scene takes place")
    tone: str = Field(description="Emotional tone, e.g. 'tense', 'heartwarming', 'mysterious'")
    arc_position: Literal["intro", "rising_action", "climax", "falling_action", "resolution"] = Field(
        description="Position in the narrative arc"
    )
    summary: str = Field(description="2-3 sentence description of what happens in this scene")
    estimated_duration_seconds: int = Field(ge=10, le=120, description="Estimated scene duration in seconds")
    themes: List[str] = Field(default_factory=list, description="Narrative themes present in this scene")


class StoryOutput(BaseModel):
    title: str = Field(description="The story title")
    genre: str = Field(description="Genre, e.g. 'sci-fi', 'fantasy', 'drama'")
    themes: List[str] = Field(description="Overall story themes")
    arc: List[Literal["intro", "rising_action", "climax", "falling_action", "resolution"]] = Field(
        description="Ordered list of arc positions present in the story"
    )
    scenes: List[Scene] = Field(description="Ordered list of scenes (3-8 scenes)")
    total_estimated_duration_seconds: int = Field(description="Sum of all scene durations in seconds")
    premise: str = Field(description="One-sentence story premise")
    setting_description: str = Field(description="Overall world/setting description for visual consistency")
