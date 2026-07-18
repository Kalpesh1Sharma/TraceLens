"""FastAPI application for ingesting and inspecting AI agent traces."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from detectors import detect_issues
from explainer import Explainer, create_explainer
from schemas import (
    ExplainedTraceIssue,
    RunTracesResponse,
    TraceEvent,
    TraceIssue,
    build_trace_tree,
)
from storage import storage
from toy_agent import build_demo_runs


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
logger = logging.getLogger(__name__)


def seed_demo_runs() -> int:
    """Persist the built-in demo traces directly through the storage boundary."""
    event_count = 0
    for events in build_demo_runs().values():
        for event in events:
            storage.store(event)
            event_count += 1
    return event_count


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.create_tables()
    if storage.is_empty():
        seeded_events = seed_demo_runs()
        logger.info("TraceLens seeded %s demo trace events into an empty database.", seeded_events)
    else:
        logger.info("TraceLens found existing trace data; skipping demo seeding.")
    app.state.explainer = create_explainer()
    yield


app = FastAPI(
    title="TraceLens",
    description="Trace ingestion and inspection for AI agent runs.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Expose the API's most useful entry points."""
    return {"service": "TraceLens", "ui": "/ui", "docs": "/docs"}


@app.get("/ui", include_in_schema=False)
def trace_replay_ui() -> FileResponse:
    """Serve the dependency-free trace replay interface."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post(
    "/traces/ingest",
    response_model=TraceEvent,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest one trace event",
)
def ingest_trace(event: TraceEvent) -> TraceEvent:
    """Validate and persist one event from an agent run."""
    return storage.store(event)


@app.get(
    "/traces/{run_id}/issues",
    response_model=list[TraceIssue],
    summary="Detect failures in a run",
)
def get_run_issues(
    run_id: str,
    timeout_threshold_ms: float = Query(default=5000.0, ge=0),
) -> list[TraceIssue]:
    """Run all failure detectors against a run's stored events."""
    return detect_issues(storage.get_run_events(run_id), timeout_threshold_ms)


@app.get(
    "/traces/{run_id}/issues/explained",
    response_model=list[ExplainedTraceIssue],
    summary="Detect failures and explain them for developers",
)
def get_explained_run_issues(
    run_id: str,
    request: Request,
    timeout_threshold_ms: float = Query(default=5000.0, ge=0),
) -> list[ExplainedTraceIssue]:
    """Run all detectors, then add provider-neutral developer explanations."""
    explainer: Explainer = request.app.state.explainer
    issues = detect_issues(storage.get_run_events(run_id), timeout_threshold_ms)
    return [
        ExplainedTraceIssue(
            **issue.model_dump(),
            ai_explanation=explainer.explain(issue),
        )
        for issue in issues
    ]


@app.get(
    "/traces/{run_id}",
    response_model=RunTracesResponse,
    summary="Get a run's chronological events and reconstructed trace tree",
)
def get_run_traces(run_id: str) -> RunTracesResponse:
    """Retrieve all events for a run, ordered by timestamp."""
    events = storage.get_run_events(run_id)
    return RunTracesResponse(run_id=run_id, events=events, tree=build_trace_tree(events))
