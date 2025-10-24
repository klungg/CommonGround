import io
import logging
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import server


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    def make_assets_dir(project_id: str) -> str:
        assets_root = tmp_path / project_id / "assets"
        assets_root.mkdir(parents=True, exist_ok=True)
        return str(assets_root)

    def resolve_asset_path(project_id: str, relative_path: str) -> str:
        assets_dir = make_assets_dir(project_id)
        normalized = os.path.normpath(os.path.join(assets_dir, relative_path))
        if not normalized.startswith(assets_dir):
            raise server.HTTPException(status_code=400, detail="Invalid path.")
        return normalized

    async def no_op_broadcast(*args, **kwargs) -> None:  # pragma: no cover
        return None

    monkeypatch.setattr(server, "_ensure_assets_dir", make_assets_dir)
    monkeypatch.setattr(server, "_resolve_asset_path", resolve_asset_path)
    monkeypatch.setattr(server, "broadcast_project_files_update", no_op_broadcast)

    original_level = server.logger.level
    server.logger.setLevel(logging.INFO)

    try:
        yield TestClient(server.app)
    finally:
        server.logger.setLevel(original_level)


def test_upload_accepts_pdf(client: TestClient) -> None:
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    files = {"files": ("example.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    response = client.post("/project/test-project/files", files=files)

    assert response.status_code == 200
    payload = response.json()
    uploaded = payload.get("uploaded", [])
    assert uploaded and uploaded[0]["name"] == "example.pdf"


def test_upload_rejects_disallowed_extension(client: TestClient) -> None:
    files = {"files": ("malware.exe", io.BytesIO(b"not real"), "application/octet-stream")}

    response = client.post("/project/test-project/files", files=files)

    assert response.status_code == 400
    assert "not allowed" in response.json().get("detail", "")
