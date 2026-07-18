"""FastAPI application for ingesting and inspecting AI agent traces."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, Request, status

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


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.create_tables()
    app.state.explainer = create_explainer()
    yield


app = FastAPI(
    title="TraceLens",
    description="Trace ingestion and inspection for AI agent runs.",
    version="0.1.0",
    lifespan=lifespan,
)


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
