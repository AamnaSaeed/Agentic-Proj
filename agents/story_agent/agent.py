"""
Phase 1 LangGraph Pipeline — Story → Character → Script

Graph topology:
  START
    └─► story_agent ──(success)──► character_agent ──(success)──► script_agent ──► END
                    └─(failure)─►                  └─(failure)─►                  ▲
                                  END                             END ─────────────┘
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from shared.schemas.pipeline_state import Phase1State
from agents.story_agent.nodes.character_node import character_agent_node
from agents.story_agent.nodes.script_node import script_agent_node
from agents.story_agent.nodes.story_node import story_agent_node

logger = logging.getLogger(__name__)


# ── Routing functions ──────────────────────────────────────────────────────

def _route_story(state: Phase1State) -> str:
    if state.get("story_output") is None:
        logger.error("Story generation failed — terminating pipeline.")
        return END
    return "character_agent"


def _route_character(state: Phase1State) -> str:
    if state.get("character_roster") is None:
        logger.error("Character generation failed — terminating pipeline.")
        return END
    return "script_agent"


# ── Graph factory ──────────────────────────────────────────────────────────

def create_phase1_graph():
    """Builds and compiles the Phase 1 LangGraph StateGraph.

    Returns:
        A compiled LangGraph runnable that accepts a Phase1State dict
        and returns the final Phase1State dict.
    """
    workflow = StateGraph(Phase1State)

    workflow.add_node("story_agent", story_agent_node)
    workflow.add_node("character_agent", character_agent_node)
    workflow.add_node("script_agent", script_agent_node)

    workflow.set_entry_point("story_agent")

    workflow.add_conditional_edges(
        "story_agent",
        _route_story,
        {"character_agent": "character_agent", END: END},
    )
    workflow.add_conditional_edges(
        "character_agent",
        _route_character,
        {"script_agent": "script_agent", END: END},
    )
    workflow.add_edge("script_agent", END)

    return workflow.compile()
