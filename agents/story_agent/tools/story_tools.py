"""
Story-level tools used by the Story Agent node.

Tools:
  - validate_story_arc  : checks narrative structure for correctness
  - estimate_duration   : estimates total video length from scene parameters
"""
from typing import List

from langchain_core.tools import tool


@tool
def validate_story_arc(arc_positions: List[str]) -> dict:
    """Validates that a story arc follows proper narrative structure.

    Args:
        arc_positions: Ordered list of arc position strings.
            Valid values: intro, rising_action, climax, falling_action, resolution.

    Returns:
        dict with keys: is_valid (bool), issues (list[str]), suggestion (str).
    """
    valid_positions = {"intro", "rising_action", "climax", "falling_action", "resolution"}
    required = {"intro", "climax", "resolution"}
    issues: List[str] = []

    arc_set = set(arc_positions)

    invalid = arc_set - valid_positions
    if invalid:
        issues.append(f"Invalid arc positions found: {sorted(invalid)}")

    missing = required - arc_set
    if missing:
        issues.append(f"Missing required arc positions: {sorted(missing)}")

    if len(arc_positions) < 3:
        issues.append("A story arc must have at least 3 positions.")

    if "intro" in arc_positions and "climax" in arc_positions:
        if arc_positions.index("intro") > arc_positions.index("climax"):
            issues.append("'intro' must appear before 'climax'.")

    if "climax" in arc_positions and "resolution" in arc_positions:
        if arc_positions.index("resolution") < arc_positions.index("climax"):
            issues.append("'resolution' must appear after 'climax'.")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "suggestion": (
            "Recommended arc: ['intro', 'rising_action', 'climax', 'falling_action', 'resolution']"
        ),
    }


@tool
def estimate_duration(
    scene_count: int,
    avg_dialogue_lines_per_scene: int,
    avg_words_per_line: int = 15,
) -> dict:
    """Estimates total animated video duration from story parameters.

    Args:
        scene_count: Number of scenes in the story.
        avg_dialogue_lines_per_scene: Average dialogue lines per scene.
        avg_words_per_line: Average word count per line (default 15).

    Returns:
        dict with estimated_total_seconds, estimated_total_minutes,
        avg_seconds_per_scene, and a human-readable recommendation.
    """
    words_per_minute = 130  # typical TTS speaking rate
    seconds_per_line = (avg_words_per_line / words_per_minute) * 60
    dialogue_per_scene = avg_dialogue_lines_per_scene * seconds_per_line
    buffer_per_scene = 5  # transitions + pauses
    avg_scene_duration = int(dialogue_per_scene + buffer_per_scene)
    total_seconds = scene_count * avg_scene_duration

    return {
        "estimated_total_seconds": total_seconds,
        "estimated_total_minutes": round(total_seconds / 60, 1),
        "avg_seconds_per_scene": avg_scene_duration,
        "recommendation": (
            f"A {scene_count}-scene story with ~{avg_dialogue_lines_per_scene} lines/scene "
            f"will run roughly {round(total_seconds / 60, 1)} minutes "
            f"({avg_scene_duration}s per scene)."
        ),
    }
