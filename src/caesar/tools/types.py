"""Shared types for Caesar's built-in tools."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class Tier(Enum):
    """A tool's execution policy.

    ONE executes immediately, TWO executes autonomously in a sandbox, and
    THREE requires explicit user approval before execution.
    """

    ONE = 1
    TWO = 2
    THREE = 3


@dataclass(frozen=True)
class ToolContext:
    """Trusted dependencies available while constructing tools."""

    agent_dir: Path
    folders: Sequence[Path]


@dataclass(frozen=True)
class Tool:
    """A model-facing capability and its execution policy."""

    name: str
    description: str
    tier: Tier
    function: Callable[..., str]

    def execute(self, **arguments: Any) -> str:
        """Run the tool's function with model-supplied arguments."""
        return self.function(**arguments)


class Toolset(Protocol):
    """A themed collection of built-in tools."""

    def list_tools(self, context: ToolContext) -> Sequence[Tool]: ...
