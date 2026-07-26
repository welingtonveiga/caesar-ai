"""Tools for reading and writing the local filesystem."""

from collections.abc import Sequence
from pathlib import Path

from caesar.tools.types import Tier, ToolContext, ToolDefinition


class FilesystemToolset:
    """Build filesystem tools with trusted paths captured from the engine."""

    def list_tools(self, context: ToolContext) -> Sequence[ToolDefinition]:
        def read_file(path: str) -> str:
            target = context.agent_dir / path
            allowed = [context.agent_dir, *context.folders]
            return _ensure_contained(target, allowed, path).read_text()

        def write_file(path: str, content: str) -> str:
            target = _ensure_contained(
                context.agent_dir / path,
                [context.agent_dir / "filesystem"],
                path,
            )
            target.write_text(content)
            return f"Wrote {path}"

        return (
            ToolDefinition(
                name="read_file",
                description="Read a UTF-8 text file from an allowed local folder.",
                tier=Tier.ONE,
                function=read_file,
            ),
            ToolDefinition(
                name="write_file",
                description="Write a UTF-8 text file inside the agent filesystem.",
                tier=Tier.ONE,
                function=write_file,
            ),
        )


def _ensure_contained(
    target: Path,
    allowed_roots: Sequence[Path],
    original_path: str,
) -> Path:
    resolved = target.resolve()
    for root in allowed_roots:
        resolved_root = root.resolve()
        if resolved.is_relative_to(resolved_root):
            return resolved
    raise ValueError(
        f"Access denied: path '{original_path}' is outside allowed directories"
    )
