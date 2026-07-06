"""
Execution engine — runs each planned task sequentially, storing intermediate
outputs and building up the full document content.
"""

import logging
from models import TaskResult
from llm_client import generate_text
from prompts import EXECUTION_PROMPT
from utils import format_completed_tasks

logger = logging.getLogger(__name__)


async def execute_plan(
    request: str,
    document_type: str,
    plan: list[str],
) -> tuple[list[TaskResult], dict[str, str]]:
    """
    Execute every task in the plan sequentially.

    For each task:
    - Build a context-aware prompt that includes all previously completed tasks.
    - Call Gemini to generate the task output.
    - Store the result in the execution log.

    The final task ("Generate Word document") is treated as a structural marker —
    its output is collected but the actual .docx is built by document_generator.py.

    Args:
        request:       The original user request.
        document_type: The document type determined by the planner.
        plan:          Ordered list of task descriptions.

    Returns:
        A tuple of:
        - execution_log: list[TaskResult] — one entry per task.
        - section_outputs: dict[str, str] — task label → generated content,
          used by the document generator to populate sections.
    """
    execution_log: list[TaskResult] = []
    section_outputs: dict[str, str] = {}

    for task in plan:
        logger.info("Executor: running task → %s", task)

        # Skip re-calling Gemini for the doc-generation marker task
        if "generate word document" in task.lower():
            logger.info("Executor: task '%s' marked as delegated.", task)
            continue

        prompt = EXECUTION_PROMPT.format(
            document_type=document_type,
            request=request,
            completed_tasks=format_completed_tasks(execution_log),
            current_task=task,
        )

        try:
            output = await generate_text(prompt, temperature=0.7)
            status = "completed"
            logger.info("Executor: task '%s' completed (%d chars).", task, len(output))
        except RuntimeError as exc:
            output = f"Task failed: {exc}"
            status = "failed"
            logger.error("Executor: task '%s' failed — %s", task, exc)

        result = TaskResult(task=task, status=status, output=output)
        execution_log.append(result)
        section_outputs[task] = output

    return execution_log, section_outputs
