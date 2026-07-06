# Autonomous Document Agent

A compact autonomous agent built for the 60-minute Python AI Engineer challenge. It accepts a natural-language business request, creates its own TODO list, executes the work sequentially, quality-checks the result, and generates a polished Microsoft Word document.

## What it demonstrates

- `POST /agent` with typed validation and useful execution metadata
- LLM-created document type, plan, and explicit assumptions
- Sequential, context-aware task execution
- Reflection/self-check with one bounded regeneration
- `.docx` generation and a safe download endpoint
- Groq, Gemini, local Ollama, and zero-setup deterministic demo modes
- Retry, exponential backoff, and fallback recovery
- Automated API, guardrail, recovery, and document tests

## Architecture

```text
POST /agent
    |
    v
Planner (LLM) ------------> document type + assumptions + TODO list
    |
    v
Executor -----------------> run each TODO with prior outputs as context
    |
    v
Reflection (LLM) ---------> pass, or regenerate once with reviewer feedback
    |
    v
python-docx --------------> formatted .docx in output/
    |
    v
JSON response ------------> plan + log + assumptions + download URL
```

The orchestration is deliberately plain Python. That keeps the control flow visible in a short code review while leaving clear seams for queues, persistence, tools, or LangGraph later.

## Quick start

Requires Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app:app --reload
```

Open Swagger at `http://127.0.0.1:8000/docs`.

The default `auto` mode selects Groq or Gemini when a key is present, and otherwise uses deterministic demo mode. Demo mode exercises the complete agent workflow and creates real Word files without credits.

### Provider configuration

Groq:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
```

Gemini:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

Ollama, fully local:

```powershell
ollama pull llama3.2:3b
ollama serve
```

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
```

Predictable no-key demo:

```dotenv
LLM_PROVIDER=mock
```

## API

### `POST /agent`

```json
{
  "request": "Create a project proposal for an AI attendance system for a university."
}
```

The response includes:

```json
{
  "status": "success",
  "document_type": "Project Proposal",
  "assumptions": ["Missing dates use practical placeholders."],
  "plan": ["Analyze the request...", "Generate Word document"],
  "execution_log": [{"task": "...", "status": "completed", "output": "..."}],
  "reflection": "Passed",
  "file": "output/project_proposal_....docx",
  "download_url": "/download/project_proposal_....docx",
  "llm_provider": "mock"
}
```

### Other endpoints

- `GET /` — health, active provider, and model
- `GET /download/{filename}` — download a generated `.docx`

Requests are restricted to 10–5000 characters, unknown JSON fields are rejected, and the download route blocks traversal and non-Word filenames.

## Two evaluation inputs

Use Swagger or [demo_requests.http](demo_requests.http).

Standard:

```text
Create a project proposal for an AI attendance system for a university.
Include objectives, scope, a six-week timeline, roles, risks, and success metrics.
```

Complex:

```text
Prepare a launch plan for an AI startup in India under INR 5 lakh. We want to
launch as quickly as possible but also require strong governance. Dates, team
size, and target customer segment are missing. Decide reasonable assumptions,
resolve the speed-versus-governance tension, and include a phased roadmap,
owners, estimated costs, risks, and measurable success criteria.
```

Run both without starting the server:

```powershell
.\.venv\Scripts\python.exe examples\run_demo.py
```

## Mandatory engineering improvement: retry and fallback

Free LLM tiers are often rate-limited or temporarily unavailable. `gemini_client.py` wraps every provider call in a bounded recovery policy:

1. Attempt the configured provider.
2. Retry transient failures up to `LLM_MAX_RETRIES` with exponential backoff.
3. Reject empty responses as failures.
4. After retries, use deterministic fallback when `ALLOW_MOCK_FALLBACK=true`.
5. If fallback is disabled, fail cleanly instead of returning a fake success.

This was chosen because provider availability is the most likely demo failure. It improves resilience without hiding the selected provider—the response and health endpoint expose it. The fallback is intentionally useful but conservative; it makes assumptions explicit and never pretends that estimates are validated facts.

The agent also includes reflection: generated content is checked for completeness and professionalism, then regenerated once if it fails. The retry limit prevents an unbounded agent loop.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Coverage includes:

- standard and complex end-to-end requests
- Word file existence, content, and download
- assumptions and execution plan visibility
- invalid request and filename guardrails
- simulated provider failure, three attempts, and fallback

## Project layout

```text
app.py                  FastAPI routes and orchestration
planner.py              LLM planning and assumption extraction
executor.py             Sequential task execution
reflection.py           Quality review and bounded regeneration
gemini_client.py         Groq/Gemini/Ollama adapters + recovery
document_generator.py   Word formatting and persistence
models.py               API and internal Pydantic models
prompts.py              Central prompt templates
tests/                   Automated tests
examples/run_demo.py     Both evaluation scenarios
VIDEO_SCRIPT.md          8–10 minute presentation runbook
```

## Tradeoff

This uses a single agent loop instead of a multi-agent framework. The gain is speed, low cognitive overhead, and a workflow that is easy to debug live. The cost is that tasks are sequential and intermediate state is in memory. At larger scale, the same planner/executor/reviewer boundaries can become queue workers backed by durable storage, with per-step timeouts, idempotency keys, and distributed tracing.

## Known production extensions

- background jobs for long requests and a `GET /jobs/{id}` endpoint
- durable plan and execution storage
- authentication, tenant isolation, quotas, and retention policies
- prompt/version telemetry and token-cost tracking
- document templates and richer table rendering
