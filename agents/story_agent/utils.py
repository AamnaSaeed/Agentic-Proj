"""
Shared utilities for Phase 1 agent nodes.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def run_tool_loop(
    llm: ChatGoogleGenerativeAI,
    tools: List[BaseTool],
    messages: List[Any],
    max_iterations: int = 6,
) -> List[Any]:
    """Runs an LLM + tool-calling loop until the model produces a response
    with no tool calls, or max_iterations is reached.

    Args:
        llm: A ChatGoogleGenerativeAI instance (no tools pre-bound).
        tools: List of LangChain tool objects to make available.
        messages: Initial message list (system + human).
        max_iterations: Safety cap on tool-call rounds.

    Returns:
        Updated messages list including all AI responses and ToolMessages.
    """
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    for iteration in range(max_iterations):
        response: AIMessage = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            logger.debug("Tool loop finished after %d iteration(s).", iteration + 1)
            break

        for tc in response.tool_calls:
            tool_name: str = tc["name"]
            tool_args: dict = tc["args"]
            logger.debug("Tool call: %s(%s)", tool_name, tool_args)

            try:
                raw_result = tool_map[tool_name].invoke(tool_args)
                result_str = (
                    json.dumps(raw_result)
                    if isinstance(raw_result, dict)
                    else str(raw_result)
                )
            except Exception as exc:
                result_str = json.dumps({"error": str(exc)})
                logger.warning("Tool '%s' raised: %s", tool_name, exc)

            messages.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"])
            )

    return messages


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Returns an OpenAI LLM instance for all Phase 1 nodes."""
    model = os.environ.get("PHASE1_MODEL", "gpt-4o")
    return ChatOpenAI(model=model, temperature=temperature)
