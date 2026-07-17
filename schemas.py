"""Pydantic models shared by the TraceLens API and storage layer."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class TraceEvent(BaseModel):
    """One recorded step in an agent run."""

    agent_id: str
    run_id: str
    step_id: str
    step_type: Literal["tool_call", "llm_call", "decision"]
    input: dict[str, Any]
    output: dict[str, Any]
    timestamp: datetime
    latency_ms: float
    status: Literal["success", "error", "timeout"]
    parent_step_id: str | None = None

    @field_validator("timestamp")
    @classmethod
    def normalise_timestamp(cls, value: datetime) -> datetime:
        """Store all timestamps in UTC so SQLite ordering is chronological."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class TraceNode(TraceEvent):
    """A trace event with its direct child steps."""

    children: list["TraceNode"] = Field(default_factory=list)


class RunTracesResponse(BaseModel):
    """Chronological events together with their reconstructed call tree."""

    run_id: str
    events: list[TraceEvent]
    tree: list[TraceNode]


class TraceIssue(BaseModel):
    """A potential failure found while analysing a run."""

    step_id: str
    issue_type: Literal["retry_loop", "tool_call_error", "silent_timeout"]
    explanation: str
    events: list[TraceEvent]


def build_trace_tree(events: list[TraceEvent]) -> list[TraceNode]:
    """Build a timestamp-sorted forest from the events in one run.

    Events whose parent is unavailable (or self-references) are returned as
    roots. ``events`` in the API response always remains the authoritative,
    complete chronological list.
    """
    nodes = {
        event.step_id: TraceNode(**event.model_dump())
        for event in events
    }
    roots: list[TraceNode] = []

    for event in events:
        node = nodes[event.step_id]
        parent = nodes.get(event.parent_step_id) if event.parent_step_id else None
        if parent is None or parent.step_id == node.step_id:
            roots.append(node)
        else:
            parent.children.append(node)

    def sort_children(node: TraceNode) -> None:
        node.children.sort(key=lambda child: child.timestamp)
        for child in node.children:
            sort_children(child)

    roots.sort(key=lambda node: node.timestamp)
    for root in roots:
        sort_children(root)
    return roots
