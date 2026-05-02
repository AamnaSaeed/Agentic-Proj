from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class VoiceConfig(BaseModel):
    gender: Literal["male", "female", "neutral"]
    age_range: Literal["child", "young_adult", "adult", "elderly"]
    tone: str = Field(description="Voice tone descriptor, e.g. 'warm', 'authoritative', 'gentle'")
    speed: float = Field(ge=0.5, le=2.0, default=1.0, description="Speaking speed multiplier")
    emotion_baseline: str = Field(description="Default emotional state, e.g. 'calm', 'enthusiastic'")
    accent: str = Field(default="neutral", description="Accent, e.g. 'american', 'british', 'neutral'")
    tts_style_tags: List[str] = Field(
        default_factory=list,
        description="Style tags for TTS synthesis, e.g. ['whispery', 'dramatic']",
    )


class AppearanceDescription(BaseModel):
    physical_description: str = Field(description="Height, build, facial features, hair colour and style")
    clothing: str = Field(description="Typical clothing or costume")
    distinctive_features: str = Field(description="Unique visual identifiers that persist across scenes")
    color_palette: List[str] = Field(description="Dominant named or hex colours associated with this character")
    art_style_prompt: str = Field(
        description="Self-contained image-generation prompt fragment for this character"
    )


class Character(BaseModel):
    character_id: str = Field(description="Unique identifier, e.g. 'char_001'")
    name: str
    role: Literal["protagonist", "antagonist", "supporting", "narrator"]
    voice_config: VoiceConfig
    appearance: AppearanceDescription
    personality_traits: List[str] = Field(description="2-6 personality traits")
    scenes_appearing_in: List[str] = Field(
        description="List of scene_ids where this character appears"
    )
    background: str = Field(description="Brief character backstory relevant to the story")


class CharacterRoster(BaseModel):
    characters: List[Character] = Field(description="All characters in the story (1-8 characters)")
    global_art_style: str = Field(
        description=(
            "Consistent art style applied to ALL visuals, e.g. "
            "'Studio Ghibli-style watercolour animation' or '3D Pixar-style CGI'"
        )
    )
