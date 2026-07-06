# 8–10 Minute Video Runbook

## 0:00–0:30 — Opening

“This is an autonomous document agent. A user supplies only a business request. The agent identifies the document type, makes missing assumptions explicit, creates its own TODO list, executes it, reviews the result, and produces a downloadable Word document.”

Keep Swagger open at `http://127.0.0.1:8000/docs` and the `output` folder visible.

## 0:30–4:00 — Live demo

1. Call `GET /`. Point out the active provider and model.
2. Send the standard input from `demo_requests.http`.
3. Show:
   - the agent-selected `document_type`
   - the generated `plan`
   - completed items in `execution_log`
   - `reflection: Passed`
   - `download_url`
4. Download and open the Word document. Show its title page styling, objectives, execution approach, timeline, risks, recommendations, and footer.
5. Send the complex input.
6. Explain that dates, team, and segment were missing and speed conflicted with governance. Show the `assumptions` and the different plan, then open the second document.

## 4:00–6:30 — What I built

Show the architecture in `README.md`, then briefly open:

- `app.py`: typed API and six-step orchestration
- `planner.py`: converts natural language to document type, assumptions, and tasks
- `executor.py`: runs each task sequentially with prior results as context
- `reflection.py`: reviewer plus one bounded regeneration
- `gemini_client.py`: Groq, Gemini, Ollama, and demo adapters
- `document_generator.py`: `python-docx` formatting and persistence

Explain why orchestration is plain Python: the state transitions are obvious in a 60-minute build, but the modules are separable for later scaling.

## 6:30–7:45 — Engineering improvement

“I implemented retry and fallback recovery. Free-tier APIs can rate-limit during a live demo. Each provider call gets bounded retries with exponential backoff. Empty output also counts as failure. If every attempt fails and fallback is enabled, the deterministic provider finishes the same workflow. If fallback is disabled, the API fails cleanly.”

Run `python -m pytest` and point out `test_retry_then_fallback`, which simulates a rate limit and verifies three provider attempts before fallback.

Also mention the reflection pass and its bounded single regeneration. It improves document quality without creating an infinite loop.

## 7:45–8:45 — Debugging insight

“One bug appeared in document assembly. An executor paragraph contained the text `Conclusion:`. The section parser interpreted that single label as if the entire document were already structured, so it skipped the fallback mapper and produced a document containing only the conclusion. The root cause was an overly weak parser condition. I changed it to require at least two recognized sections; otherwise it maps task outputs into executive summary, objectives, main content, recommendations, and conclusion. The end-to-end test now opens the `.docx` and asserts that key sections exist.”

## 8:45–9:30 — Tradeoff and close

“I chose a single-agent sequential architecture over a multi-agent framework. It is faster to build, easier to explain, and has deterministic control flow. The tradeoff is in-memory state and sequential latency. For production I would move executions to background jobs, persist every step, add idempotency and tracing, and parallelize independent tasks.”

Close by showing `7+ passed` and both generated Word files.
