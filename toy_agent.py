"""Post deterministic demo agent traces to a running TraceLens API.

Run ``uvicorn main:app --reload`` first, then execute
``python toy_agent.py``. The script posts a retry-loop run and an error run.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from schemas import TraceEvent


def build_demo_runs() -> dict[str, list[TraceEvent]]:
    """Build two realistic, deterministic runs with intentional failures."""
    started_at = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    retry_run_id = "demo-retry-loop"
    error_run_id = "demo-tool-error"

    retry_events = [
        TraceEvent(
            agent_id="research-agent",
            run_id=retry_run_id,
            step_id=f"retry-search-{attempt}",
            step_type="tool_call",
            input={"tool": "web_search", "query": "TraceLens architecture"},
            output={"results": 0, "attempt": attempt},
            timestamp=started_at + timedelta(seconds=attempt),
            latency_ms=240.0 + attempt,
            status="success",
            parent_step_id=None,
        )
        for attempt in range(1, 4)
    ]
    retry_events.extend(
        [
            TraceEvent(
                agent_id="research-agent",
                run_id=retry_run_id,
                step_id="retry-parse",
                step_type="tool_call",
                input={"tool": "parse_results", "format": "html"},
                output={"documents": 0},
                timestamp=started_at + timedelta(seconds=4),
                latency_ms=38.0,
                status="success",
                parent_step_id="retry-search-3",
            ),
            TraceEvent(
                agent_id="research-agent",
                run_id=retry_run_id,
                step_id="retry-decide",
                step_type="decision",
                input={"available_documents": 0},
                output={"action": "respond_with_no_results"},
                timestamp=started_at + timedelta(seconds=5),
                latency_ms=22.0,
                status="success",
                parent_step_id="retry-parse",
            ),
            TraceEvent(
                agent_id="research-agent",
                run_id=retry_run_id,
                step_id="retry-respond",
                step_type="llm_call",
                input={"template": "no_search_results"},
                output={"message": "No matching sources were found."},
                timestamp=started_at + timedelta(seconds=6),
                latency_ms=310.0,
                status="success",
                parent_step_id="retry-decide",
            ),
        ]
    )

    error_events = [
        TraceEvent(
            agent_id="research-agent",
            run_id=error_run_id,
            step_id="error-search",
            step_type="tool_call",
            input={"tool": "web_search", "query": "FastAPI background tasks"},
            output={"results": [{"url": "https://example.com/article"}]},
            timestamp=started_at + timedelta(minutes=1),
            latency_ms=182.0,
            status="success",
            parent_step_id=None,
        ),
        TraceEvent(
            agent_id="research-agent",
            run_id=error_run_id,
            step_id="error-parse",
            step_type="tool_call",
            input={"tool": "parse_results", "format": "html"},
            output={"error": "Parser could not read the source document."},
            timestamp=started_at + timedelta(minutes=1, seconds=1),
            latency_ms=96.0,
            status="error",
            parent_step_id="error-search",
        ),
        TraceEvent(
            agent_id="research-agent",
            run_id=error_run_id,
            step_id="error-decide",
            step_type="decision",
            input={"parse_status": "error"},
            output={"action": "send_partial_response"},
            timestamp=started_at + timedelta(minutes=1, seconds=2),
            latency_ms=19.0,
            status="success",
            parent_step_id="error-parse",
        ),
        TraceEvent(
            agent_id="research-agent",
            run_id=error_run_id,
            step_id="error-respond",
            step_type="llm_call",
            input={"template": "partial_response"},
            output={},
            timestamp=started_at + timedelta(minutes=1, seconds=3),
            latency_ms=6200.0,
            status="timeout",
            parent_step_id="error-decide",
        ),
    ]
    return {retry_run_id: retry_events, error_run_id: error_events}


def post_event(event: TraceEvent, api_base_url: str) -> None:
    """Send one event to TraceLens using only the Python standard library."""
    body = json.dumps(event.model_dump(mode="json")).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/traces/ingest",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        if response.status != 201:
            raise RuntimeError(f"TraceLens returned HTTP {response.status}")


def main() -> None:
    api_base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    try:
        for run_id, events in build_demo_runs().items():
            for event in events:
                post_event(event, api_base_url)
            print(f"Posted {len(events)} events for {run_id}.")
    except (HTTPError, URLError) as error:
        raise SystemExit(f"Could not post traces to {api_base_url}: {error}") from error


if __name__ == "__main__":
    main()
