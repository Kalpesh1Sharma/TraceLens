"""FastAPI application for ingesting and inspecting AI agent traces."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, status

from schemas import RunTracesResponse, TraceEvent, build_trace_tree
from storage import storage


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.create_tables()
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
    "/traces/{run_id}",
    response_model=RunTracesResponse,
    summary="Get a run's chronological events and reconstructed trace tree",
)
def get_run_traces(run_id: str) -> RunTracesResponse:
    """Retrieve all events for a run, ordered by timestamp."""
    events = storage.get_run_events(run_id)
    return RunTracesResponse(run_id=run_id, events=events, tree=build_trace_tree(events))
