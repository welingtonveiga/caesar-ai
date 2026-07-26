"""Registry and execution entry points for built-in tools."""

from typing import Any

from caesar.tools.filesystem import FilesystemToolset
from caesar.tools.types import ToolContext, ToolDefinition, Toolset
from caesar.tools.web_access import WebAccessToolset

_TOOLSETS: tuple[Toolset, ...] = (FilesystemToolset(), WebAccessToolset())


def list_tools(context: ToolContext) -> list[ToolDefinition]:
    """Return every built-in tool configured with trusted runtime context."""
    return [tool for toolset in _TOOLSETS for tool in toolset.list_tools(context)]


def execute_tool(tool: ToolDefinition, arguments: dict[str, Any]) -> str:
    """Execute a listed tool with model-supplied arguments."""
    return tool.function(**arguments)
