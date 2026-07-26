"""Shared types for Caesar's built-in tools."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class Tier(Enum):
    """A tool's execution policy.

    ONE executes immediately, TWO executes autonomously in a sandbox, and
    THREE requires explicit user approval before execution.
    """

    ONE = 1
    TWO = 2
    THREE = 3


class WebClient(Protocol):
    """The web operations required by Caesar's web tools."""

    def fetch(self, url: str) -> str: ...

    def search(self, query: str) -> str: ...


@dataclass(frozen=True)
class ToolContext:
    """Trusted dependencies available while constructing tools."""

    agent_dir: Path
    folders: Sequence[Path]
    web_client: WebClient


@dataclass(frozen=True)
class ToolDefinition:
    """A tool's model-facing declaration and execution policy."""

    name: str
    description: str
    tier: Tier
    function: Callable[..., str]


class Toolset(Protocol):
    """A themed collection of built-in tools."""

    def list_tools(self, context: ToolContext) -> Sequence[ToolDefinition]: ...
