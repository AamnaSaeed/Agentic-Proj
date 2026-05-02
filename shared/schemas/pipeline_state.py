"""
LangGraph state object shared across all Phase 1 nodes.
Uses Annotated reducer so errors/tools_log are appended, not overwritten.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import TypedDict


class Phase1State(TypedDict):
    user_prompt: str
    story_output: Optional[Dict[str, Any]]
    character_roster: Optional[Dict[str, Any]]
    script_output: Optional[Dict[str, Any]]
    # Reducers: each node appends to these lists instead of replacing them
    errors: Annotated[List[str], operator.add]
    tools_log: Annotated[List[Dict[str, Any]], operator.add]
    retry_counts: Dict[str, int]
