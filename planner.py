"""
Planner module — responsible for understanding the user request and producing
an ordered execution plan via Gemini.
"""

import logging
from llm_client import generate_text
from prompts import PLANNER_PROMPT
from utils import extract_json

logger = logging.getLogger(__name__)


async def create_plan(request: str) -> tuple[str, list[str], list[str]]:
    """
    Ask Gemini to analyse the business request and return:
    - The most appropriate document type.
    - An ordered list of tasks (the execution plan / TODO list).

    Args:
        request: The raw natural-language business request from the user.

    Returns:
        A tuple of (document_type, plan_tasks).

    Raises:
        ValueError: If Gemini returns an unparseable response.
        RuntimeError: If the Gemini API call fails.
    """
    logger.info("Planner: generating plan for request (first 80 chars): %s", request[:80])

    prompt = PLANNER_PROMPT.format(request=request)
    raw_response = await generate_text(prompt, temperature=0.3)

    logger.debug("Planner raw response: %s", raw_response)

    parsed = extract_json(raw_response)

    document_type: str = parsed.get("document_type", "Business Document")
    plan: list[str] = parsed.get("plan", [])
    assumptions: list[str] = parsed.get("assumptions", [])

    if not isinstance(plan, list) or not plan:
        raise ValueError("Planner returned an empty plan. Cannot proceed.")
    # Small local models sometimes ignore the requested task-count limit.
    # Keep four actionable LLM tasks plus the deterministic document step so
    # local execution remains useful and demo-friendly.
    plan = [
        str(task).strip()
        for task in plan
        if str(task).strip() and "generate word document" not in str(task).lower()
    ][:4]
    if not plan:
        plan = [
            "Analyze the request, constraints, and assumptions",
            "Define objectives, scope, and success measures",
            "Develop the solution, timeline, ownership, and resources",
            "Assess risks, mitigations, and final recommendations",
        ]

    request_lower = request.lower()
    plan_text = " ".join(plan).lower()
    required_additions: list[str] = []
    if any(word in request_lower for word in ("risk", "mitigation")) and "risk" not in plan_text:
        required_additions.append("assess risks and mitigations")
    if any(word in request_lower for word in ("budget", "cost", "lakh")) and not any(
        word in plan_text for word in ("budget", "cost", "resource")
    ):
        required_additions.append("estimate costs and resources")
    if required_additions:
        plan[-1] = f"{plan[-1]}; " + "; ".join(required_additions)
    assumptions = [str(item).strip() for item in assumptions if str(item).strip()][:8]

    # Guarantee the final step is always doc generation
    plan.append("Generate Word document")

    logger.info("Planner: document_type=%s, tasks=%d", document_type, len(plan))
    return document_type, plan, assumptions
