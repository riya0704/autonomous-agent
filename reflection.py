"""
Reflection module — implements self-review and optional regeneration.

After the initial document content is assembled, the agent asks Gemini to
review it against quality criteria. If the review fails, one regeneration
attempt is made (MAX_REFLECTION_RETRIES = 1).
"""

import logging
from llm_client import generate_text
from models import ReflectionResult
from prompts import REFLECTION_PROMPT, REGENERATION_PROMPT
from utils import extract_json
from config import settings

logger = logging.getLogger(__name__)


async def reflect_on_document(
    request: str,
    document_type: str,
    document_content: str,
) -> tuple[ReflectionResult, str]:
    """
    Ask Gemini to review the assembled document content.

    If the review fails and MAX_REFLECTION_RETRIES > 0, the document is
    regenerated once using the reviewer's feedback.

    Args:
        request:          The original user request.
        document_type:    The document type (e.g. "Project Proposal").
        document_content: The full text content of the document (all sections joined).

    Returns:
        A tuple of:
        - ReflectionResult — contains passed flag, feedback, and regenerated flag.
        - Final document content string (possibly improved after regeneration).
    """
    logger.info("Reflection: starting quality review.")

    review_prompt = REFLECTION_PROMPT.format(
        document_type=document_type,
        request=request,
        document_content=document_content,
    )

    raw_review = await generate_text(review_prompt, temperature=0.2)
    logger.debug("Reflection raw response: %s", raw_review)

    try:
        parsed = extract_json(raw_review)
        passed: bool = bool(parsed.get("passed", False))
        feedback: str = parsed.get("feedback", "No feedback provided.")
    except ValueError:
        # If JSON parsing fails, treat as passed to avoid blocking the pipeline
        logger.warning("Reflection: could not parse review JSON. Treating as passed.")
        passed = True
        feedback = "Review parsing failed — treated as passed."

    logger.info("Reflection: passed=%s | feedback=%s", passed, feedback[:120])

    if passed:
        return ReflectionResult(passed=True, feedback=feedback, regenerated=False), document_content

    # --- Reflection failed: attempt one regeneration ---
    if settings.MAX_REFLECTION_RETRIES < 1:
        logger.info("Reflection: failed but MAX_REFLECTION_RETRIES=0, skipping regeneration.")
        return ReflectionResult(passed=False, feedback=feedback, regenerated=False), document_content

    logger.info("Reflection: document failed review. Regenerating (attempt 1 of 1).")

    regen_prompt = REGENERATION_PROMPT.format(
        document_type=document_type,
        request=request,
        feedback=feedback,
        document_content=document_content,
    )

    try:
        improved_content = await generate_text(regen_prompt, temperature=0.6)
        logger.info("Reflection: regeneration complete (%d chars).", len(improved_content))
        return (
            ReflectionResult(passed=False, feedback=feedback, regenerated=True),
            improved_content,
        )
    except RuntimeError as exc:
        logger.error("Reflection: regeneration failed — %s", exc)
        return (
            ReflectionResult(passed=False, feedback=feedback, regenerated=False),
            document_content,
        )
