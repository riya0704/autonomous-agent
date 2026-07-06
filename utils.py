"""
Utility helpers used across the agent.
"""

import json
import logging
import re
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_filename(document_type: str) -> str:
    """
    Generate a unique filename for the output Word document.

    Format: <slug>_<timestamp>_<short_uuid>.docx

    Args:
        document_type: Human-readable document type (e.g. "Project Proposal").

    Returns:
        A filename string suitable for use on all platforms.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", document_type).strip("_").lower()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return f"{slug}_{timestamp}_{short_id}.docx"


def extract_json(text: str) -> dict:
    """
    Robustly extract the first JSON object from a string.

    Gemini sometimes wraps JSON in markdown code fences — this handles that.

    Args:
        text: Raw text that should contain a JSON object.

    Returns:
        Parsed dictionary.

    Raises:
        ValueError: If no valid JSON object is found.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse JSON from model response: {exc}") from exc

    raise ValueError("No JSON object found in model response.")


def format_completed_tasks(task_results: list) -> str:
    """
    Format a list of TaskResult objects into a readable string for prompt injection.

    Args:
        task_results: List of TaskResult instances.

    Returns:
        A multi-line string summarising completed tasks and their outputs.
    """
    if not task_results:
        return "None"
    parts = []
    for idx, result in enumerate(task_results, start=1):
        parts.append(f"Task {idx}: {result.task}\nOutput:\n{result.output}\n")
    return "\n".join(parts)
