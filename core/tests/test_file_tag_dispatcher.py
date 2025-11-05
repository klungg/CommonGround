import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import file_tag_dispatcher


@pytest.fixture
def assets_dir(tmp_path: Path) -> Path:
    assets = tmp_path / "assets"
    assets.mkdir()
    return assets


@pytest.fixture(autouse=True)
def patch_path_resolvers(monkeypatch: pytest.MonkeyPatch, assets_dir: Path) -> None:
    def _ensure_assets_dir(_project_id: str) -> str:
        return str(assets_dir)

    def _resolve_asset_path(_project_id: str, relative_path: str) -> str:
        return str((assets_dir / relative_path).resolve())

    monkeypatch.setattr(file_tag_dispatcher, "_ensure_assets_dir", _ensure_assets_dir)
    monkeypatch.setattr(file_tag_dispatcher, "_resolve_asset_path", _resolve_asset_path)


def test_resolve_text_file(assets_dir: Path) -> None:
    target = assets_dir / "notes" / "readme.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Hello World!", encoding="utf-8")

    resolution = file_tag_dispatcher.resolve_tagged_file_parts(
        project_id="demo",
        payload={"file_tags": [{"relative_path": "notes/readme.md", "is_directory": False}]},
    )

    assert len(resolution.parts) == 1
    assert resolution.parts[0]["type"] == "text"
    assert "Hello World" in resolution.parts[0]["text"]
    assert len(resolution.text_blocks) == 1
    assert "--- notes/readme.md ---" in resolution.text_blocks[0]
    assert "Hello World" in resolution.text_blocks[0]
    assert resolution.absolute_files[0].endswith("notes/readme.md")
    assert resolution.errors == []
    assert resolution.warnings == []
    assert len(resolution.attachments) == 1
    attachment = resolution.attachments[0]
    assert attachment.relative_path == "notes/readme.md"
    assert not attachment.is_directory


def test_resolve_binary_file(assets_dir: Path) -> None:
    target = assets_dir / "diagram.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n")

    resolution = file_tag_dispatcher.resolve_tagged_file_parts(
        project_id="demo",
        payload={"file_tags": [{"relative_path": "diagram.png", "is_directory": False}]},
    )

    assert len(resolution.parts) == 1
    inline_part = resolution.parts[0]
    assert inline_part["type"] == "input_image"
    data_url = inline_part["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")
    encoded = data_url.split(",", 1)[1]
    assert base64.b64decode(encoded) == b"\x89PNG\r\n\x1a\n"
    assert resolution.text_blocks == []
    assert resolution.absolute_files[0].endswith("diagram.png")


def test_directory_resolution_limits(assets_dir: Path) -> None:
    directory = assets_dir / "docs"
    directory.mkdir()
    (directory / "a.txt").write_text("A", encoding="utf-8")
    (directory / "b.txt").write_text("B", encoding="utf-8")

    resolution = file_tag_dispatcher.resolve_tagged_file_parts(
        project_id="demo",
        payload={"file_tags": [{"relative_path": "docs", "is_directory": True}]},
    )

    assert any(part.get("type") == "text" and part.get("text", "").startswith("--- docs/a.txt") for part in resolution.parts)
    assert any(part.get("type") == "text" and part.get("text", "").startswith("--- docs/b.txt") for part in resolution.parts)
    assert any(block.startswith("--- docs/a.txt ---") for block in resolution.text_blocks)
    assert any(block.startswith("--- docs/b.txt ---") for block in resolution.text_blocks)
    assert any(path.endswith("docs") for path in resolution.absolute_files)
    attachment_paths = {meta.relative_path for meta in resolution.attachments}
    assert "docs" in attachment_paths  # directory entry
    assert "docs/a.txt" in attachment_paths
    assert "docs/b.txt" in attachment_paths


def test_missing_file_records_error(assets_dir: Path) -> None:
    resolution = file_tag_dispatcher.resolve_tagged_file_parts(
        project_id="demo",
        payload={"file_tags": [{"relative_path": "missing.txt", "is_directory": False}]},
    )

    assert resolution.parts == []
    assert resolution.attachments == []
    assert resolution.errors
