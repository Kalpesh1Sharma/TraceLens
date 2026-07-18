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
The trace replay UI is available at `http://127.0.0.1:8000/ui`.
SQLite data is stored in `tracelens.db` beside the application.

## Endpoints

- `POST /traces/ingest` validates and stores one trace event.
- `GET /traces/{run_id}` returns `events`, a complete timestamp-sorted list, and
  `tree`, a timestamp-sorted parent/child reconstruction of those events.
- `GET /traces/{run_id}/issues` returns retry loops, tool-call errors, and
  timeouts. Use `?timeout_threshold_ms=7500` to override the 5000ms default.
- `GET /traces/{run_id}/issues/explained` returns the same issues enriched with
  a plain-English `ai_explanation` field.

## AI explanations

To enable Groq-generated explanations, set an API key before starting Uvicorn:

```powershell
$env:GROQ_API_KEY = "your-groq-api-key"
uvicorn main:app --reload
```

TraceLens uses `llama-3.3-70b-versatile` through the Groq Python SDK. The
prompt is restricted to the detector output and associated event data. If
`GROQ_API_KEY` is not set, startup logs that TraceLens is using its rule-based
fallback explainer; all explanation endpoints continue to work offline.

## Demo data and detector check

With the API running, post two deterministic demo runs (one retry loop and one
tool error plus a timeout):

```powershell
python toy_agent.py
```

Run the detector check without starting the API:

```powershell
python -m unittest discover -s tests -v
```

## Trace replay UI

Open `/ui` to load a run as a step-by-step timeline. Flagged steps are shown
with a warning treatment; click one to reveal its issue type and explanation.
After posting the demo data with `python toy_agent.py`, use either quick-load
button to inspect `demo-retry-loop` or `demo-tool-error` without entering a run
ID manually.

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
