"""
Pydantic models for request/response validation and internal data structures.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# API request model
# ---------------------------------------------------------------------------

class AgentRequest(BaseModel):
    """Incoming request payload for the /agent endpoint."""

    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=10, max_length=5000)

    @field_validator("request")
    @classmethod
    def validate_request(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Request must not be empty.")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in v):
            raise ValueError("Request contains unsupported control characters.")
        return v


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

class TaskResult(BaseModel):
    """Holds the result of a single executed task."""

    task: str
    status: str          # "completed" | "failed"
    output: str
    timestamp: str = ""

    def __init__(self, **data: Any):
        if "timestamp" not in data or not data["timestamp"]:
            data["timestamp"] = datetime.utcnow().isoformat() + "Z"
        super().__init__(**data)


class ReflectionResult(BaseModel):
    """Holds the outcome of the self-review / reflection step."""

    passed: bool
    feedback: str
    regenerated: bool = False


# ---------------------------------------------------------------------------
# API response model
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Final JSON response returned by the /agent endpoint."""

    status: str
    request: str
    document_type: str
    assumptions: list[str] = Field(default_factory=list)
    plan: list[str]
    execution_log: list[TaskResult]
    reflection: str
    file: str
    download_url: str
    generated_at: str = ""

    def __init__(self, **data: Any):
        if "generated_at" not in data or not data["generated_at"]:
            data["generated_at"] = datetime.utcnow().isoformat() + "Z"
        super().__init__(**data)
