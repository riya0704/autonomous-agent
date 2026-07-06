"""Configuration for the local document agent."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
    OLLAMA_BASE_URL: str = os.getenv(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    ).rstrip("/")
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "450"))
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")
    MAX_REFLECTION_RETRIES: int = int(os.getenv("MAX_REFLECTION_RETRIES", "1"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    ALLOW_MOCK_FALLBACK: bool = os.getenv(
        "ALLOW_MOCK_FALLBACK", "true"
    ).lower() in {"1", "true", "yes", "on"}
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def resolve_provider(self) -> str:
        """Return Ollama or the deterministic test fallback."""
        return self.LLM_PROVIDER

    def active_model(self) -> str:
        """Return the configured local model name."""
        return self.OLLAMA_MODEL if self.LLM_PROVIDER == "ollama" else "test-fallback"

    def validate(self) -> None:
        """Validate bounded settings and create the output directory."""
        if self.LLM_PROVIDER not in {"ollama", "mock"}:
            raise EnvironmentError("LLM_PROVIDER must be ollama or mock.")
        if not 0 <= self.LLM_MAX_RETRIES <= 5:
            raise EnvironmentError("LLM_MAX_RETRIES must be between 0 and 5.")
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)


settings = Settings()
