"""
FastAPI application entry point.

Exposes:
  POST /agent  — accepts a natural-language business request and returns
                 a plan, execution log, reflection result, and .docx path.
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from config import settings
from models import AgentRequest, AgentResponse, TaskResult
from planner import create_plan
from executor import execute_plan
from reflection import reflect_on_document
from document_generator import build_document

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validate environment on startup
# ---------------------------------------------------------------------------
settings.validate()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Autonomous Document Service",
    description=(
        "An autonomous workflow that accepts a natural-language business request, "
        "creates an execution plan using Gemini, runs every task sequentially, "
        "performs self-reflection, and generates a professional Word document."
    ),
    version="1.0.0",
    contact={"name": "AI Agent API"},
    license_info={"name": "MIT"},
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a clean 422 when Pydantic validation fails."""
    errors = [{"field": e["loc"][-1], "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"status": "error", "errors": errors})


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected server errors."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error. Check logs."},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def health_check() -> dict:
    """Quick health-check endpoint."""
    return {
        "status": "ok",
        "service": "Autonomous Document Service",
    }


@app.post(
    "/agent",
    response_model=AgentResponse,
    summary="Run the autonomous agent",
    tags=["Agent"],
    responses={
        200: {
            "description": "Agent completed successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "request": "Create a project proposal for an AI Attendance System",
                        "document_type": "Project Proposal",
                        "plan": [
                            "Understand the request and define scope",
                            "Identify document type and structure",
                            "Create proposal outline",
                            "Generate business content",
                            "Review completeness",
                            "Generate Word document",
                        ],
                        "execution_log": [
                            {
                                "task": "Understand the request and define scope",
                                "status": "completed",
                                "output": "...",
                                "timestamp": "2024-01-01T12:00:00Z",
                            }
                        ],
                        "reflection": "Passed",
                        "file": "output/project_proposal_20240101_120000_abc12345.docx",
                        "generated_at": "2024-01-01T12:00:05Z",
                    }
                }
            },
        },
        422: {"description": "Validation error (empty / too-short request)."},
        500: {"description": "Internal server error."},
    },
)
async def run_agent(body: AgentRequest) -> AgentResponse:
    """
    Autonomous agent endpoint.

    Workflow:
    1. **Plan** — Gemini analyses the request and produces a TODO list + document type.
    2. **Execute** — Each task is run sequentially; outputs are stored.
    3. **Assemble** — All section outputs are joined into a single content string.
    4. **Reflect** — Gemini reviews the assembled content; regenerates once if needed.
    5. **Generate** — python-docx builds the final Word document.
    6. **Respond** — Returns JSON with plan, execution log, reflection status, and file path.
    """
    request_text = body.request
    logger.info("=== New agent request (first 80 chars): %s ===", request_text[:80])

    # 1. Plan
    document_type, plan, assumptions = await create_plan(request_text)
    logger.info("Plan created: %d tasks for '%s'", len(plan), document_type)

    # 2. Execute
    execution_log, section_outputs = await execute_plan(request_text, document_type, plan)

    # 3. Assemble full content for reflection
    assembled_content = _assemble_content(section_outputs)

    # 4. Reflect
    reflection_result, final_content = await reflect_on_document(
        request=request_text,
        document_type=document_type,
        document_content=assembled_content,
    )

    reflection_status = _build_reflection_status(reflection_result)

    # 5. Generate document
    file_path = build_document(
        document_type=document_type,
        request=request_text,
        section_outputs=section_outputs,
        final_content=final_content,
    )
    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        raise RuntimeError("Document generator did not produce a valid file.")

    # Log the doc-generation task result
    execution_log.append(
        TaskResult(
            task="Generate Word document",
            status="completed",
            output=f"Document saved at {file_path}",
        )
    )

    logger.info("=== Agent completed. File: %s ===", file_path)

    return AgentResponse(
        status="success",
        request=request_text,
        document_type=document_type,
        assumptions=assumptions,
        plan=plan,
        execution_log=execution_log,
        reflection=reflection_status,
        file=file_path,
        download_url=f"/download/{os.path.basename(file_path)}",
    )


@app.get(
    "/download/{filename}",
    summary="Download a generated document",
    tags=["Documents"],
    response_class=FileResponse,
)
async def download_document(filename: str) -> Response:
    """
    Download a previously generated Word document by filename.

    Args:
        filename: The .docx filename (not the full path).
    """
    # Sanitise to prevent path traversal
    safe_name = os.path.basename(filename)
    if safe_name != filename or not safe_name.lower().endswith(".docx"):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid document filename."},
        )
    file_path = os.path.join(settings.OUTPUT_DIR, safe_name)

    if not os.path.isfile(file_path):
        return JSONResponse(status_code=404, content={"status": "error", "message": "File not found."})

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_name,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assemble_content(section_outputs: dict[str, str]) -> str:
    """Join all executor outputs into a single string for reflection."""
    parts = []
    for task, output in section_outputs.items():
        parts.append(f"### {task}\n{output}")
    return "\n\n".join(parts)


def _build_reflection_status(reflection_result) -> str:
    """Convert ReflectionResult into a human-readable status string."""
    if reflection_result.passed:
        return "Passed"
    if reflection_result.regenerated:
        return "Failed — Regenerated"
    return "Failed — Not Regenerated (retry limit reached)"
