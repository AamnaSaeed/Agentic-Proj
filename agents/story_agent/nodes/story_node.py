"""
Story Agent Node — Phase 1, Step 1.

Generates a structured StoryOutput (title, genre, scenes, arc) from
the raw user prompt, using validate_story_arc and estimate_duration tools.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from shared.schemas.pipeline_state import Phase1State
from shared.schemas.story_schema import StoryOutput
from agents.story_agent.tools.story_tools import estimate_duration, validate_story_arc
from agents.story_agent.utils import get_llm, run_tool_loop

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a master creative story architect specialising in short animated films.

Your task: transform a user prompt into a detailed story structure for a 2–5 minute animated short.

Requirements:
- 4–6 distinct scenes with vivid settings and emotional tones
- A clear narrative arc: intro → rising_action → climax → (falling_action) → resolution
- Cohesive themes woven throughout
- Total estimated duration 90–300 seconds

Available tools:
• validate_story_arc  — call this to verify your arc before finalising
• estimate_duration   — call this to sense-check the video length

Workflow:
1. Draft your story outline mentally.
2. Call validate_story_arc with your planned arc positions.
3. Call estimate_duration with your scene count and expected dialogue density.
4. Adjust if needed, then wait for the structured-output request.
"""


def story_agent_node(state: Phase1State) -> Dict[str, Any]:
    """LangGraph node: generates StoryOutput from state['user_prompt']."""
    logger.info("Story agent: generating story for prompt: '%s...'", state["user_prompt"][:60])

    tools = [validate_story_arc, estimate_duration]
    tools_log: List[Dict[str, Any]] = []

    messages: List[Any] = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Create a complete story structure for this prompt:\n\n"
                f"\"{state['user_prompt']}\"\n\n"
                "First use validate_story_arc and estimate_duration to validate your plan, "
                "then I will ask you for the final structured output."
            )
        ),
    ]

    try:
        llm = get_llm(temperature=0.7)
        messages = run_tool_loop(llm, tools, messages)

        # Record tool usage
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_log.append(
                        {"node": "story_agent", "tool": tc["name"], "args": tc["args"]}
                    )

        # Extract structured output via a separate zero-temperature call
        structured_llm = get_llm(temperature=0).with_structured_output(StoryOutput)
        story: StoryOutput = structured_llm.invoke(
            messages
            + [
                HumanMessage(
                    content=(
                        "Now produce the final structured StoryOutput JSON. "
                        "Use scene_ids like 'scene_001', 'scene_002', etc. "
                        "Every scene must have an arc_position, tone, setting, summary, "
                        "and estimated_duration_seconds."
                    )
                )
            ]
        )

        logger.info(
            "Story agent done: '%s' — %d scenes, ~%ds",
            story.title,
            len(story.scenes),
            story.total_estimated_duration_seconds,
        )
        return {
            "story_output": story.model_dump(),
            "tools_log": tools_log,
            "errors": [],
        }

    except Exception as exc:
        logger.error("Story agent failed: %s", exc)
        return {
            "story_output": None,
            "tools_log": tools_log,
            "errors": [f"story_agent error: {exc}"],
        }
