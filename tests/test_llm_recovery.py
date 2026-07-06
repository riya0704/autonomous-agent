import asyncio

import llm_client
from config import settings


def test_retry_then_fallback(monkeypatch) -> None:
    attempts = 0

    async def failing_provider(provider: str, prompt: str, temperature: float) -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("simulated rate limit")

    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(llm_client, "_call_provider", failing_provider)
    monkeypatch.setattr(llm_client.asyncio, "sleep", no_wait)

    prompt = "AUTONOMOUS_PLANNER\nBUSINESS_REQUEST:\nCreate a business report\nEND_REQUEST"
    result = asyncio.run(llm_client.generate_text(prompt))

    assert attempts == 3
    assert '"document_type": "Business Report"' in result
