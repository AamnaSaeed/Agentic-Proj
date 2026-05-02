"""
Character Agent Node — Phase 1, Step 2.

Generates a CharacterRoster (names, voices, appearances, scene assignments)
from the StoryOutput produced by the story node.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from shared.schemas.character_schema import CharacterRoster
from shared.schemas.pipeline_state import Phase1State
from agents.story_agent.tools.character_tools import check_consistency
from agents.story_agent.utils import get_llm, run_tool_loop

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a character designer and casting director for animated films.

Given a story structure, create a complete character roster with:
- Unique character_ids (char_001, char_002, …)
- Rich visual appearance descriptions suitable for AI image generation
- Voice configurations for TTS synthesis (gender, age_range, tone, speed, emotion_baseline, accent, tts_style_tags)
- Consistent personalities that serve the narrative
- A global_art_style that will be applied uniformly to ALL scene visuals

Guidelines:
- The protagonist (char_001) must appear in most scenes.
- Voice configs must be distinct enough for listeners to tell characters apart.
- art_style_prompt inside each character's appearance should be a self-contained
  fragment that can be appended to any scene prompt (e.g. "young woman with red curly hair,
  wearing a blue astronaut suit, determined expression").
- global_art_style examples: "Studio Ghibli-style watercolour anime",
  "3D Pixar-style CGI", "2D flat-design cartoon", "hand-drawn ink-wash illustration".

Available tool:
• check_consistency — call this with your character_ids and scene-character map to
  verify every character appears in at least one scene and no scene references an
  undefined character.
"""


def character_agent_node(state: Phase1State) -> Dict[str, Any]:
    """LangGraph node: generates CharacterRoster from state['story_output']."""
    if not state.get("story_output"):
        return {
            "character_roster": None,
            "errors": ["character_agent: story_output is missing — cannot generate characters."],
            "tools_log": [],
        }

    story = state["story_output"]
    scene_ids = [s["scene_id"] for s in story.get("scenes", [])]
    logger.info("Character agent: designing roster for story '%s'", story.get("title", ""))

    tools = [check_consistency]
    tools_log: List[Dict[str, Any]] = []
    story_context = json.dumps(story, indent=2)

    messages: List[Any] = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Design the full character roster for this story:\n\n{story_context}\n\n"
                f"Scene IDs present: {scene_ids}\n\n"
                "For each character specify which scene_ids they appear in. "
                "Then call check_consistency to validate your assignments."
            )
        ),
    ]

    try:
        llm = get_llm(temperature=0.7)
        messages = run_tool_loop(llm, tools, messages)

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_log.append(
                        {"node": "character_agent", "tool": tc["name"], "args": tc["args"]}
                    )

        structured_llm = get_llm(temperature=0).with_structured_output(CharacterRoster)
        roster: CharacterRoster = structured_llm.invoke(
            messages
            + [
                HumanMessage(
                    content=(
                        "Now produce the final CharacterRoster JSON. "
                        "Ensure character_ids are 'char_001', 'char_002', etc. "
                        "Every scene_id in scenes_appearing_in must match a scene_id "
                        "from the story exactly. Include global_art_style."
                    )
                )
            ]
        )

        logger.info(
            "Character agent done: %d characters, art style: '%s'",
            len(roster.characters),
            roster.global_art_style,
        )
        return {
            "character_roster": roster.model_dump(),
            "tools_log": tools_log,
            "errors": [],
        }

    except Exception as exc:
        logger.error("Character agent failed: %s", exc)
        return {
            "character_roster": None,
            "tools_log": tools_log,
            "errors": [f"character_agent error: {exc}"],
        }
