# TraceLens

A small FastAPI service for ingesting and inspecting AI-agent trace events.

## Run locally

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the API from this directory:

```powershell
uvicorn main:app --reload
```

The interactive API documentation is available at `http://127.0.0.1:8000/docs`.
SQLite data is stored in `tracelens.db` beside the application.

## Endpoints

- `POST /traces/ingest` validates and stores one trace event.
- `GET /traces/{run_id}` returns `events`, a complete timestamp-sorted list, and
  `tree`, a timestamp-sorted parent/child reconstruction of those events.

Example event:

```json
{
  "agent_id": "research-agent",
  "run_id": "run-123",
  "step_id": "search-web",
  "step_type": "tool_call",
  "input": {"query": "TraceLens"},
  "output": {"results": 3},
  "timestamp": "2026-07-17T12:30:00Z",
  "latency_ms": 248.7,
  "status": "success",
  "parent_step_id": null
}
```
