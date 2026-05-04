"""
Base Tool Interface for MCP Layer.
All tools must inherit from BaseTool and implement execute().
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """Abstract base class for all MCP tools."""

    name: str = "base_tool"
    description: str = "Base tool interface"

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters. Returns a result dict."""
        raise NotImplementedError

    def validate_inputs(self, required_keys: list, kwargs: dict):
        """Utility: raise ValueError if any required key is missing."""
        missing = [k for k in required_keys if k not in kwargs]
        if missing:
            raise ValueError(f"[{self.name}] Missing required inputs: {missing}")