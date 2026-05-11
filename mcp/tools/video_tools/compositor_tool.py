"""
compositor_tool.py — MoviePy-based Video Compositor (Phase 3)

Assembles per-scene video clips (with audio already embedded) into a final
MP4 with:
  - Crossfade transitions between scenes
  - Optional title card at start
  - Optional end card
  - Consistent resolution / fps

Uses MoviePy 1.0.3.
"""

import os
import json
from pathlib import Path

from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from mcp.base_tool import BaseTool

try:
    from moviepy import (
        VideoFileClip,
        ImageClip,
        ColorClip,
        TextClip,
        CompositeVideoClip,
        concatenate_videoclips,
        AudioFileClip,
    )
    MOVIEPY_OK = True
except ImportError:
    MOVIEPY_OK = False


def create_title_card(
    title: str,
    duration: float = 3.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    output_path: str = None,
) -> "VideoFileClip":
    """Create a simple dark title card with white text."""
    bg = ColorClip(size=(width, height), color=(10, 10, 20), duration=duration)
    try:
        txt = TextClip(
            text=title,
            font_size=52,
            color="white",
            duration=duration,
        ).with_position("center")
        card = CompositeVideoClip([bg, txt]).with_fps(fps)
    except Exception:
        card = bg.with_fps(fps)

    if output_path:
        card.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            preset="fast",
            audio=False,
            logger=None,
        )
    return card


def composite_with_moviepy(
    scene_clip_paths: List[str],
    output_path: str,
    story_title: str = "",
    transition_duration: float = 0.8,
    fps: int = 24,
    width: int = 1280,
    height: int = 720,
    add_title_card: bool = True,
    add_end_card: bool = True,
) -> str:
    """
    Load per-scene MP4s, add crossfade transitions, and export final_output.mp4.
    """
    if not MOVIEPY_OK:
        raise RuntimeError("MoviePy not installed.")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    clips = []

    # Optional title card
    if add_title_card and story_title:
        print(f"  [compositor] Creating title card: '{story_title}'")
        title_clip = ColorClip(
            size=(width, height), color=(10, 10, 20), duration=3.0
        ).with_fps(fps)
        try:
            txt = TextClip(
                text=story_title,
                font_size=52,
                color="white",
                duration=3.0,
            ).with_position("center")
            title_clip = CompositeVideoClip([title_clip, txt]).with_fps(fps)
        except Exception as e:
            print(f"  [compositor] TextClip failed ({e}), skipping title text.")
        clips.append(title_clip)

    # Load scene clips
    loaded = []
    for p in scene_clip_paths:
        if not os.path.exists(p):
            print(f"  [compositor] WARNING: clip not found: {p}")
            continue
        clip = VideoFileClip(p).with_fps(fps)
        if clip.size != (width, height):
            clip = clip.resized((width, height))
        loaded.append(clip)
        print(f"  [compositor] Loaded {Path(p).name} ({clip.duration:.1f}s)")

    if not loaded:
        raise RuntimeError("No scene clips found — cannot composite.")

    clips.extend(loaded)

    # Optional end card
    if add_end_card:
        end_clip = ColorClip(
            size=(width, height), color=(10, 10, 20), duration=2.0
        ).with_fps(fps)
        try:
            end_txt = TextClip(
                text="— The End —",
                font_size=46,
                color="white",
                duration=2.0,
            ).with_position("center")
            end_clip = CompositeVideoClip([end_clip, end_txt]).with_fps(fps)
        except Exception:
            pass
        clips.append(end_clip)

    # Concatenate with crossfade transitions
    print(f"  [compositor] Concatenating {len(clips)} clips with {transition_duration}s crossfades…")
    if transition_duration > 0 and len(clips) > 1:
        final = concatenate_videoclips(
            clips,
            method="compose",
            padding=-transition_duration,
            transition=None,
        )
    else:
        final = concatenate_videoclips(clips, method="compose")

    final = final.with_fps(fps)

    print(f"  [compositor] Writing final video → {output_path}")
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        preset="fast",
        audio_codec="aac",
        audio_bitrate="192k",
        threads=4,
        logger=None,
    )

    # Cleanup
    for c in loaded:
        c.close()

    return output_path


# ── MCP Tool class ─────────────────────────────────────────────────────────────

class CompositorTool(BaseTool):
    """MCP tool: composite scene clips into final MP4 using MoviePy."""

    name = "compositor_tool"
    description = "Assembles scene clips with transitions into final_output.mp4."

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_inputs(["scene_clip_paths", "output_path"], kwargs)
        path = composite_with_moviepy(
            scene_clip_paths=kwargs["scene_clip_paths"],
            output_path=kwargs["output_path"],
            story_title=kwargs.get("story_title", ""),
            transition_duration=kwargs.get("transition_duration", 0.8),
            fps=kwargs.get("fps", 24),
            width=kwargs.get("width", 1280),
            height=kwargs.get("height", 720),
            add_title_card=kwargs.get("add_title_card", True),
            add_end_card=kwargs.get("add_end_card", True),
        )
        return {"success": True, "output_path": path}