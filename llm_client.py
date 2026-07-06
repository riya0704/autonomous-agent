"""Local Ollama client with bounded retry and deterministic test fallback."""

import asyncio
import json
import logging
import re
from urllib import error, request

from config import settings

logger = logging.getLogger(__name__)


def _http_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.LLM_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {body[:500]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM connection failed: {exc.reason}") from exc


def _generate_with_ollama(prompt: str, temperature: float) -> str:
    body = _http_json(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        {
            "model": settings.active_model(),
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": settings.OLLAMA_NUM_PREDICT,
            },
        },
        {},
    )
    return body["response"].strip()


def _between(prompt: str, start: str, end: str | None = None) -> str:
    tail = prompt.split(start, 1)[-1]
    if end and end in tail:
        tail = tail.split(end, 1)[0]
    return tail.strip().strip('"')


def _mock_generate(prompt: str) -> str:
    """Deterministic zero-setup mode used for demos and provider outages."""
    if "AUTONOMOUS_PLANNER" in prompt:
        user_request = _between(prompt, "BUSINESS_REQUEST:", "END_REQUEST")
        lowered = user_request.lower()
        if "sop" in lowered or "standard operating" in lowered:
            doc_type = "Standard Operating Procedure"
        elif "technical" in lowered or "architecture" in lowered:
            doc_type = "Technical Design"
        elif "minutes" in lowered:
            doc_type = "Meeting Minutes"
        elif "proposal" in lowered:
            doc_type = "Project Proposal"
        elif "plan" in lowered or "roadmap" in lowered:
            doc_type = "Project Plan"
        else:
            doc_type = "Business Report"
        assumptions = [
            "Where the request omits owners or dates, practical placeholders are used.",
            "Figures are planning estimates and should be validated before approval.",
        ]
        if "startup" in lowered and "india" in lowered:
            assumptions = [
                "Launch target is eight weeks from approval.",
                "Initial segment is Indian B2B SMEs seeking workflow automation.",
                "A four-person core team uses contractors for specialist legal and design work.",
                "The planning ceiling is INR 5 lakh; the proposed allocation is INR 4.8 lakh.",
            ]
        elif "attendance" in lowered:
            assumptions = [
                "The first release is a six-week pilot for one campus and approximately 2,000 students.",
                "The university provides identity-system access and a faculty product owner.",
                "The pilot uses QR/RFID check-in; biometric processing is out of scope unless separately approved.",
            ]
        return json.dumps(
            {
                "document_type": doc_type,
                "assumptions": assumptions,
                "plan": [
                    "Analyze the request, constraints, and reasonable assumptions",
                    "Define objectives, scope, and success measures",
                    "Develop the core strategy, timeline, ownership, and resource estimates",
                    "Assess risks, define mitigations, and produce final recommendations",
                    "Generate Word document",
                ],
            }
        )

    if "QUALITY_REVIEWER" in prompt:
        content = _between(prompt, "DOCUMENT_CONTENT:", "END_DOCUMENT")
        passed = len(content) >= 900 and not re.search(r"\bTask failed:", content)
        return json.dumps(
            {
                "passed": passed,
                "feedback": (
                    "Content is sufficiently detailed, actionable, and professionally structured."
                    if passed
                    else "Expand the content and ensure objectives, actions, risks, and recommendations are complete."
                ),
            }
        )

    if "DOCUMENT_REGENERATOR" in prompt:
        request_text = _between(prompt, "BUSINESS_REQUEST:", "END_REQUEST")
        return _mock_full_document(request_text)

    if "TASK_EXECUTOR" in prompt:
        request_text = _between(prompt, "BUSINESS_REQUEST:", "END_REQUEST")
        task = _between(prompt, "CURRENT_TASK:", "END_CURRENT_TASK")
        return _mock_task_content(request_text, task)

    return "Generated content for the requested business document."


def _mock_task_content(user_request: str, task: str) -> str:
    request_excerpt = " ".join(user_request.split())[:350]
    request_lower = user_request.lower()
    is_startup = "startup" in request_lower and "india" in request_lower
    is_attendance = "attendance" in request_lower
    lower = task.lower()
    if ("strategy" in lower or "approach" in lower) and (
        "timeline" in lower or "resource" in lower
    ):
        return (
            _mock_task_content(user_request, "Develop the core strategy and execution approach")
            + "\n\n"
            + _mock_task_content(user_request, "Create timeline, ownership, and resource estimates")
        )
    if "analyze" in lower:
        return (
            f"The requested outcome is: {request_excerpt}. The document will prioritize a practical, "
            "decision-ready result while making missing details explicit.\n"
            "- Primary audience: sponsor, delivery lead, and operational stakeholders\n"
            "- Constraints: stated budget, timing, and scope take precedence\n"
            "- Assumption policy: use conservative estimates and flag items requiring validation"
        )
    if "objective" in lower:
        if is_attendance:
            return (
                "Objectives\n"
                "- Pilot a secure digital attendance workflow for 2,000 students within six weeks.\n"
                "- Achieve at least 98% successful check-ins and reduce faculty administration time by 60%.\n"
                "- Provide role-based dashboards, exception handling, and auditable attendance exports.\n"
                "- Obtain privacy, security, faculty, and student sign-off before broader rollout.\n"
                "Out of scope: payroll, grading, and biometric identification without separate approval."
            )
        if is_startup:
            return (
                "Objectives\n"
                "- Validate one painful workflow for Indian SMEs with 20 interviews and five design partners.\n"
                "- Launch a sellable MVP within eight weeks while staying below INR 5 lakh.\n"
                "- Win three paying pilot customers and reach INR 75,000 monthly recurring revenue within 90 days.\n"
                "- Establish minimum governance for privacy, contracts, model evaluation, and incident ownership."
            )
        return (
            "Objectives\n"
            "- Deliver the requested business outcome with a clear and measurable scope.\n"
            "- Establish accountable owners, milestones, and acceptance criteria.\n"
            "- Reduce delivery risk through early validation and staged execution.\n"
            "Success measures: stakeholder approval, milestones completed on schedule, budget variance "
            "within 10%, and documented operational handover."
        )
    if "strategy" in lower or "approach" in lower:
        if is_attendance:
            return (
                "Solution and Delivery Approach\n"
                "1. Discover: map enrollment, timetable, attendance, correction, and reporting workflows.\n"
                "2. Design: use student QR/RFID check-in, faculty confirmation, an exception queue, and admin reports.\n"
                "3. Build: deliver authentication, class roster sync, offline-safe capture, dashboards, and audit logs.\n"
                "4. Pilot: run with two departments, compare digital records to manual ground truth, and collect feedback.\n"
                "5. Gate rollout: expand only after accuracy, privacy, uptime, and support criteria pass."
            )
        if is_startup:
            return (
                "Lean Launch Strategy\n"
                "1. Target Indian B2B SMEs with 20–200 employees and repetitive document-heavy workflows.\n"
                "2. Select one use case through interviews; require urgency, measurable ROI, and accessible data.\n"
                "3. Build a narrow human-in-the-loop MVP using a hosted open-source model or free-tier API.\n"
                "4. Sell five paid pilots through founder-led outreach and two channel partners.\n"
                "5. Govern speed with weekly release gates covering quality, privacy, security, and customer approval."
            )
        return (
            "Execution Approach\n"
            "1. Discover: confirm stakeholders, baseline, constraints, and decision criteria.\n"
            "2. Design: agree the target process, deliverables, and measurable acceptance criteria.\n"
            "3. Deliver: implement in short checkpoints with visible progress and issue tracking.\n"
            "4. Validate: run stakeholder review, quality checks, and a controlled pilot.\n"
            "5. Handover: document ownership, training, support, and continuous-improvement actions."
        )
    if "timeline" in lower or "resource" in lower:
        if is_startup:
            return (
                "Eight-Week Roadmap and Ownership\n"
                "- Weeks 1–2 — Founder/CEO: 20 interviews, segment scorecard, five design partners.\n"
                "- Weeks 3–4 — Technical Lead: MVP, evaluation set, logs, access controls, and human review.\n"
                "- Weeks 5–6 — Growth Lead: onboard pilots, pricing tests, contracts, and support playbook.\n"
                "- Weeks 7–8 — Founders: convert pilots, publish evidence, and make the scale/pivot decision.\n"
                "Budget Estimate (INR)\n"
                "- Customer discovery and design: 50,000\n"
                "- MVP engineering and contractors: 160,000\n"
                "- Cloud, tools, and model usage: 50,000\n"
                "- Sales and launch marketing: 100,000\n"
                "- Legal, privacy, and accounting: 40,000\n"
                "- Contingency: 80,000\n"
                "- Total: 480,000 (within the INR 500,000 ceiling)"
            )
        return (
            "Indicative Timeline and Ownership\n"
            "- Week 1 — Sponsor/Product Owner: approve scope and success criteria.\n"
            "- Weeks 2–3 — Delivery Team: design and create the first working deliverable.\n"
            "- Week 4 — Business SMEs: validate through review or pilot.\n"
            "- Weeks 5–6 — Delivery Lead: refine, launch, and hand over operations.\n"
            "Use a small cross-functional team: sponsor, delivery lead, subject-matter expert, writer/"
            "analyst, and reviewer. Final staffing and costs require sponsor confirmation."
        )
    if "risk" in lower:
        extra = ""
        if is_startup:
            extra = (
                "\n- Slow willingness to pay — require paid pilots and a stop/pivot gate after week six."
                "\n- AI quality or privacy incident — use evaluation thresholds, human approval, minimal retention, and an incident owner."
            )
        elif is_attendance:
            extra = (
                "\n- Proxy attendance or QR sharing — rotate session codes and require faculty exception review."
                "\n- Student privacy concerns — minimize data, publish retention rules, and complete a privacy review."
            )
        return (
            "Key Risks and Mitigations\n"
            "- Ambiguous scope — confirm exclusions and acceptance criteria at kickoff.\n"
            "- Unvalidated assumptions — maintain an assumption log with owners and due dates.\n"
            "- Schedule pressure — prioritize must-have outcomes and time-box reviews.\n"
            "- Stakeholder availability — book decision checkpoints in advance.\n"
            "- Quality or adoption gaps — pilot with representative users and capture evidence."
            + extra
        )
    return (
        "Recommendations\n"
        "- Approve a short discovery checkpoint before committing the full budget.\n"
        "- Assign one accountable owner and use weekly milestone reviews.\n"
        "- Validate estimates, dependencies, and assumptions with stakeholders.\n"
        "- Start with the smallest useful release, measure outcomes, then expand.\n"
        "Conclusion: the proposed staged approach balances speed, governance, and adaptability while "
        "leaving clear decision points for information that is not yet available."
    )


def _mock_full_document(user_request: str) -> str:
    return "\n\n".join(
        [
            "EXECUTIVE SUMMARY:\n" + _mock_task_content(user_request, "analyze"),
            "OBJECTIVES:\n" + _mock_task_content(user_request, "objectives"),
            "MAIN CONTENT:\n" + _mock_task_content(user_request, "strategy")
            + "\n\n" + _mock_task_content(user_request, "timeline"),
            "RECOMMENDATIONS:\n" + _mock_task_content(user_request, "risks")
            + "\n\n" + _mock_task_content(user_request, "review"),
            "CONCLUSION:\nProceed through staged approval, validation, delivery, and handover.",
        ]
    )


async def _call_provider(provider: str, prompt: str, temperature: float) -> str:
    if provider == "ollama":
        return await asyncio.to_thread(_generate_with_ollama, prompt, temperature)
    if provider == "mock":
        return _mock_generate(prompt)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


async def generate_text(prompt: str, temperature: float = 0.7) -> str:
    """Generate text, retrying transient failures and optionally falling back."""
    provider = settings.resolve_provider()
    last_error: Exception | None = None
    for attempt in range(settings.LLM_MAX_RETRIES + 1):
        try:
            text = await _call_provider(provider, prompt, temperature)
            if not text:
                raise RuntimeError("LLM returned an empty response.")
            return text
        except Exception as exc:
            last_error = exc
            logger.warning(
                "LLM provider '%s' failed (attempt %d/%d): %s",
                provider,
                attempt + 1,
                settings.LLM_MAX_RETRIES + 1,
                exc,
            )
            if attempt < settings.LLM_MAX_RETRIES:
                await asyncio.sleep(0.5 * (2**attempt))

    if provider != "mock" and settings.ALLOW_MOCK_FALLBACK:
        logger.error("Primary provider unavailable; using deterministic fallback.")
        return _mock_generate(prompt)
    raise RuntimeError(f"LLM generation failed after retries: {last_error}") from last_error
