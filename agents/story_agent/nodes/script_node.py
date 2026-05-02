"""
Script Agent Node — Phase 1, Step 3.

Generates the full ScriptOutput (dialogue, visual prompts, timing, camera
moves) from the StoryOutput + CharacterRoster.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from shared.schemas.pipeline_state import Phase1State
from shared.schemas.script_schema import ScriptOutput
from agents.story_agent.tools.script_tools import (
    analyze_emotions,
    build_visual_prompt,
    validate_duration,
)
from agents.story_agent.tools.story_tools import estimate_duration
from agents.story_agent.utils import get_llm, run_tool_loop

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a professional screenplay writer specialising in animated short films.

Given a story structure and character roster, write a complete scene-by-scene script with:
- Natural, character-appropriate dialogue (2–5 lines per scene)
- Precise timing_offset_seconds for each line (cumulative from scene start)
- Detailed visual_prompt for image generation (incorporating characters + setting + art style)
- camera_movement, transition_in, transition_out, background_music_mood per scene
- estimated_duration_seconds consistent with the story's estimates

Available tools (use each at least once):
• build_visual_prompt  — call for each scene to build a production-quality image prompt
• analyze_emotions     — call for each dialogue line to get the TTS emotion tag
• validate_duration    — call per scene to check dialogue fits the target duration
• estimate_duration    — call to verify overall pacing

Important:
- visual_prompt must embed the global_art_style from the character roster.
- All scene_ids in ScriptOutput.scenes must exactly match scene_ids in StoryOutput.
- All character_ids in dialogue lines must exactly match character_ids in CharacterRoster.
- line_ids use format 'line_001', 'line_002', etc. (reset per scene).
"""


def script_agent_node(state: Phase1State) -> Dict[str, Any]:
    """LangGraph node: generates ScriptOutput from story + character roster."""
    if not state.get("story_output") or not state.get("character_roster"):
        return {
            "script_output": None,
            "errors": [
                "script_agent: story_output or character_roster is missing — cannot write script."
            ],
            "tools_log": [],
        }

    story = state["story_output"]
    roster = state["character_roster"]
    logger.info("Script agent: writing script for '%s'", story.get("title", ""))

    tools = [build_visual_prompt, analyze_emotions, validate_duration, estimate_duration]
    tools_log: List[Dict[str, Any]] = []

    context = json.dumps({"story": story, "characters": roster}, indent=2)

    messages: List[Any] = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Write the complete script for this story and character roster:\n\n{context}\n\n"
                "For EACH scene:\n"
                "1. Call build_visual_prompt → use the result as visual_prompt.\n"
                "2. Write 2–5 dialogue lines.\n"
                "3. Call analyze_emotions for each line → use the result as the emotion tag.\n"
                "4. Call validate_duration → adjust if dialogue is too long.\n\n"
                "After processing all scenes, I will ask for the final structured output."
            )
        ),
    ]

    try:
        llm = get_llm(temperature=0.7)
        messages = run_tool_loop(llm, tools, messages, max_iterations=10)

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_log.append(
                        {"node": "script_agent", "tool": tc["name"], "args": tc["args"]}
                    )

        structured_llm = get_llm(temperature=0).with_structured_output(ScriptOutput)
        script: ScriptOutput = structured_llm.invoke(
            messages
            + [
                HumanMessage(
                    content=(
                        "Now produce the final ScriptOutput JSON. "
                        "Include one SceneScript for EVERY scene in the story. "
                        "scene_ids must match the story exactly. "
                        "character_ids in dialogue must match the roster exactly. "
                        "line_ids use format 'line_001', 'line_002', … (reset per scene)."
                    )
                )
            ]
        )

        total_lines = sum(len(s.dialogue) for s in script.scenes)
        logger.info(
            "Script agent done: %d scenes, %d total dialogue lines",
            len(script.scenes),
            total_lines,
        )
        return {
            "script_output": script.model_dump(),
            "tools_log": tools_log,
            "errors": [],
        }

    except Exception as exc:
        logger.error("Script agent failed: %s", exc)
        return {
            "script_output": None,
            "tools_log": tools_log,
            "errors": [f"script_agent error: {exc}"],
        }
