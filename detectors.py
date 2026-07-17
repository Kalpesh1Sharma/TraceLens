"""Failure detectors for TraceLens agent runs."""

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator

from schemas import TraceEvent, TraceIssue, TraceNode


def _flatten_events(events: Iterable[TraceEvent | TraceNode]) -> Iterator[TraceEvent]:
    """Yield events from either a flat list or one or more trace-tree roots."""
    visited: set[int] = set()

    def walk(event: TraceEvent | TraceNode) -> Iterator[TraceEvent]:
        if id(event) in visited:
            return
        visited.add(id(event))
        yield event
        if isinstance(event, TraceNode):
            for child in event.children:
                yield from walk(child)

    for event in events:
        yield from walk(event)


def _canonical_input(value: dict) -> str:
    """Create a stable grouping key for semantically identical JSON inputs."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def detect_retry_loops(
    events: Iterable[TraceEvent | TraceNode], minimum_repetitions: int = 3
) -> list[TraceIssue]:
    """Flag a step type/input combination that occurs repeatedly in one run."""
    if minimum_repetitions < 2:
        raise ValueError("minimum_repetitions must be at least 2")

    groups: dict[tuple[str, str, str], list[TraceEvent]] = defaultdict(list)
    for event in _flatten_events(events):
        groups[(event.run_id, event.step_type, _canonical_input(event.input))].append(event)

    issues: list[TraceIssue] = []
    for (_, step_type, _), matching_events in groups.items():
        if len(matching_events) < minimum_repetitions:
            continue
        matching_events.sort(key=lambda event: event.timestamp)
        issues.append(
            TraceIssue(
                step_id=matching_events[-1].step_id,
                issue_type="retry_loop",
                explanation=(
                    f"{step_type} repeated {len(matching_events)} times with the same input."
                ),
                events=matching_events,
            )
        )
    return issues


def detect_tool_call_errors(events: Iterable[TraceEvent | TraceNode]) -> list[TraceIssue]:
    """Flag tool calls whose status explicitly reports an error."""
    return [
        TraceIssue(
            step_id=event.step_id,
            issue_type="tool_call_error",
            explanation="Tool call completed with an error status.",
            events=[event],
        )
        for event in _flatten_events(events)
        if event.step_type == "tool_call" and event.status == "error"
    ]


def detect_silent_timeouts(
    events: Iterable[TraceEvent | TraceNode], timeout_threshold_ms: float = 5000.0
) -> list[TraceIssue]:
    """Flag explicit timeouts and slow steps that returned no output."""
    if timeout_threshold_ms < 0:
        raise ValueError("timeout_threshold_ms must not be negative")

    issues: list[TraceIssue] = []
    for event in _flatten_events(events):
        explicit_timeout = event.status == "timeout"
        slow_without_output = event.latency_ms > timeout_threshold_ms and not event.output
        if not (explicit_timeout or slow_without_output):
            continue

        if explicit_timeout:
            explanation = "Step reported a timeout status."
        else:
            explanation = (
                f"Step took {event.latency_ms:g}ms, exceeding the "
                f"{timeout_threshold_ms:g}ms threshold, and returned no output."
            )
        issues.append(
            TraceIssue(
                step_id=event.step_id,
                issue_type="silent_timeout",
                explanation=explanation,
                events=[event],
            )
        )
    return issues


def detect_issues(
    events: Iterable[TraceEvent | TraceNode], timeout_threshold_ms: float = 5000.0
) -> list[TraceIssue]:
    """Run every built-in detector and return the combined issue list."""
    flattened_events = list(_flatten_events(events))
    return [
        *detect_retry_loops(flattened_events),
        *detect_tool_call_errors(flattened_events),
        *detect_silent_timeouts(flattened_events, timeout_threshold_ms),
    ]
