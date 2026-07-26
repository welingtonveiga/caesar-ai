"""Registry for built-in tools."""

from caesar.tools.filesystem import FilesystemToolset
from caesar.tools.types import Tool, ToolContext, Toolset
from caesar.tools.web_access import WebAccessToolset

_TOOLSETS: tuple[Toolset, ...] = (FilesystemToolset(), WebAccessToolset())


def list_tools(context: ToolContext) -> list[Tool]:
    """Return every built-in tool configured with trusted runtime context."""
    return [tool for toolset in _TOOLSETS for tool in toolset.list_tools(context)]
