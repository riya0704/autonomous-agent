"""Run both evaluation scenarios without starting an HTTP server."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import run_agent
from models import AgentRequest


REQUESTS = [
    (
        "STANDARD",
        "Create a project proposal for an AI attendance system for a university. "
        "Include objectives, scope, a six-week timeline, roles, risks, and success metrics.",
    ),
    (
        "COMPLEX",
        "Prepare a launch plan for an AI startup in India under INR 5 lakh. We want to "
        "launch quickly but require strong governance. Dates, team size, and target customer "
        "segment are missing. Decide reasonable assumptions and include a phased roadmap, "
        "owners, costs, risks, and measurable success criteria.",
    ),
]


async def main() -> None:
    for label, request in REQUESTS:
        result = await run_agent(AgentRequest(request=request))
        print(f"\n=== {label} ===")
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
