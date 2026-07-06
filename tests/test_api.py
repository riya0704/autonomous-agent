from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import app
from config import settings


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_standard_request_creates_downloadable_docx(client: TestClient) -> None:
    response = client.post(
        "/agent",
        json={
            "request": (
                "Create a project proposal for an AI attendance system for a university, "
                "including scope, timeline, risks, and success metrics."
            )
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["document_type"] == "Project Proposal"
    assert len(payload["plan"]) >= 5
    assert all(item["status"] == "completed" for item in payload["execution_log"])

    path = Path(payload["file"])
    assert path.exists() and path.suffix == ".docx"
    document_text = "\n".join(p.text for p in Document(path).paragraphs)
    assert "Objectives" in document_text
    assert "Key Risks" in document_text
    assert "Conclusion" in document_text

    download = client.get(payload["download_url"])
    assert download.status_code == 200
    assert download.content[:2] == b"PK"  # DOCX is an Open XML ZIP archive.


def test_complex_request_makes_and_returns_assumptions(client: TestClient) -> None:
    response = client.post(
        "/agent",
        json={
            "request": (
                "Prepare a launch plan for an AI startup in India under INR 5 lakh, "
                "launch quickly but include strong governance. Dates, team size, and "
                "customer segment are missing; decide reasonable assumptions and include "
                "a roadmap, owners, costs, risks, and measurable success criteria."
            )
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["document_type"] == "Project Plan"
    assert payload["assumptions"]
    assert payload["reflection"] == "Passed"
    assert Path(payload["file"]).stat().st_size > 1_000


@pytest.mark.parametrize(
    "body",
    [
        {"request": "short"},
        {"request": "          "},
        {"request": "A valid request body", "unexpected": True},
    ],
)
def test_request_guardrails_return_422(client: TestClient, body: dict) -> None:
    response = client.post("/agent", json=body)
    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_download_rejects_non_docx(client: TestClient) -> None:
    response = client.get("/download/secrets.txt")
    assert response.status_code == 400
