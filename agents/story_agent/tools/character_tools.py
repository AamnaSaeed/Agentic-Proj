"""
Character-level tools used by the Character Agent node.

Tools:
  - check_consistency : validates character-scene assignments are coherent
"""
from typing import Dict, List

from langchain_core.tools import tool


@tool
def check_consistency(
    character_ids: List[str],
    scene_character_map: Dict[str, List[str]],
) -> dict:
    """Checks that character-scene assignments are internally consistent.

    Args:
        character_ids: List of all defined character_id strings.
        scene_character_map: Dict mapping scene_id to the list of
            character_ids that appear in that scene.

    Returns:
        dict with: is_consistent (bool), issues (list[str]),
        coverage summary, and recommendations.
    """
    issues: List[str] = []
    char_set = set(character_ids)

    # Every character referenced in a scene must be defined
    for scene_id, chars in scene_character_map.items():
        undefined = [c for c in chars if c not in char_set]
        if undefined:
            issues.append(
                f"Scene '{scene_id}' references undefined character(s): {undefined}"
            )

    # Characters that appear in no scene are wasted definitions
    all_used: set = set()
    for chars in scene_character_map.values():
        all_used.update(chars)

    never_used = char_set - all_used
    if never_used:
        issues.append(
            f"Character(s) defined but never assigned to a scene: {sorted(never_used)}"
        )

    # Protagonist should appear in more than one scene
    protagonist_scene_count = sum(
        1
        for chars in scene_character_map.values()
        if any(c.endswith("_001") or "protagonist" in c.lower() for c in chars)
    )
    if protagonist_scene_count < 2 and len(scene_character_map) >= 3:
        issues.append(
            "The protagonist should appear in at least 2 scenes for narrative continuity."
        )

    return {
        "is_consistent": len(issues) == 0,
        "issues": issues,
        "total_characters_defined": len(character_ids),
        "total_characters_used": len(all_used),
        "coverage": f"{len(all_used)}/{len(character_ids)} characters appear in at least one scene",
        "recommendation": (
            "All characters accounted for."
            if not issues
            else "Fix the issues above before finalising the character roster."
        ),
    }
