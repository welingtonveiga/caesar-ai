"""Approval data shared between the brain and channel layers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovalRequest:
    """A persisted Tier 3 action awaiting a deterministic decision."""

    chat_id: int
    tool_call_id: str
    tool: str
    path: str
    content_summary: str | None
