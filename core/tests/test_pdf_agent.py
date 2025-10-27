import io
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import pdf_agent_service  # noqa: E402
from api import server  # noqa: E402
from api.pdf_agent_service import PdfAgentConfig, run_pdf_to_markdown  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_run_pdf_to_markdown_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Dict[str, Any]] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if kwargs.get("model") == "step1-model":
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Draft line\n" + ("A" * 200),
                        }
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {
                        "content": "# Final Heading\n\nBody text",
                    }
                }
            ]
        }

    monkeypatch.setattr(pdf_agent_service, "_call_bridge_completion", fake_completion)

    config = PdfAgentConfig(
        step1_model="step1-model",
        step2_model="step2-model",
        max_file_mb=2,
    )

    pdf_bytes = b"%PDF-1.4\nmock"
    result = await run_pdf_to_markdown(pdf_bytes=pdf_bytes, filename="sample.pdf", config=config)

    assert len(calls) == 2
    assert result["draft_markdown"].startswith("Draft line")
    assert result["final_markdown"].startswith("# Final Heading")
    assert result["step1_model"] == "step1-model"
    assert result["step2_model"] == "step2-model"


def test_pdf_endpoint_returns_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_completion(**kwargs):
        if kwargs.get("model") == "openai/gemini-2.5-flash":
            return {"choices": [{"message": {"content": "Draft"}}]}
        return {"choices": [{"message": {"content": "# Final"}}]}

    monkeypatch.setattr(pdf_agent_service, "_call_bridge_completion", fake_completion)

    client = TestClient(server.app)

    files = {"file": ("example.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}

    response = client.post("/pdf/to-markdown", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["final_markdown"] == "# Final"
