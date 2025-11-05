import base64
import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from agent_core.iic.core.iic_handlers import get_iic_dir


MAX_SINGLE_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_FILES_PER_DIRECTORY = 40
MAX_TEXT_CHARACTERS = 40_000


TEXT_FALLBACK_EXTENSIONS = {
    '.md', '.markdown', '.txt', '.py', '.ts', '.tsx', '.js', '.jsx', '.json',
    '.yml', '.yaml', '.toml', '.ini', '.cfg', '.env', '.xml', '.html', '.css', '.scss',
}


logger = logging.getLogger(__name__)
def _ensure_assets_dir(project_id: str) -> str:
    project_path_str = get_iic_dir(project_id)
    if not project_path_str or not os.path.isdir(project_path_str):
        raise HTTPException(status_code=404, detail=f"Project with ID '{project_id}' not found.")

    assets_dir = os.path.join(project_path_str, "assets")
    try:
        os.makedirs(assets_dir, exist_ok=True)
    except OSError as exc:
        logger.error(
            "assets_directory_creation_failed",
            extra={"assets_dir": assets_dir, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Could not create assets directory on the server.")

    return os.path.abspath(assets_dir)


def _resolve_asset_path(project_id: str, relative_path: str) -> str:
    assets_dir = _ensure_assets_dir(project_id)
    normalized = os.path.normpath(os.path.join(assets_dir, relative_path))

    if not normalized.startswith(assets_dir):
        raise HTTPException(status_code=400, detail="Invalid path.")

    return normalized


@dataclass
class AttachmentMetadata:
    relative_path: str
    is_directory: bool
    size_bytes: int
    mime_type: str | None


@dataclass
class FileTagResolution:
    parts: List[Any]
    text_blocks: List[str]
    attachments: List[AttachmentMetadata]
    warnings: List[str]
    errors: List[str]
    absolute_files: List[str]


def _is_text_file(path: str, mime_type: str | None) -> bool:
    if mime_type and mime_type.startswith('text/'):
        return True
    if mime_type in {'application/json', 'application/javascript'}:
        return True
    _, ext = os.path.splitext(path)
    return ext.lower() in TEXT_FALLBACK_EXTENSIONS


def _is_image_file(mime_type: str | None) -> bool:
    return bool(mime_type and mime_type.startswith('image/'))


def _read_text_file(path: str) -> Tuple[str, bool]:
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        content = handle.read(MAX_TEXT_CHARACTERS + 1)
    truncated = len(content) > MAX_TEXT_CHARACTERS
    if truncated:
        content = content[:MAX_TEXT_CHARACTERS] + '\n[... truncated ...]'
    return content, truncated


def _make_text_part(header: str, body: str | None = None) -> Dict[str, Any]:
    content = header if body is None else f"{header}\n\n{body}"
    return {
        "type": "text",
        "text": content,
    }


def _make_image_part(path: str, mime_type: str, data: bytes) -> Dict[str, Any]:
    data_url = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
    return {
        "type": "input_image",
        "image_url": {"url": data_url, "details": "high"},
    }


def _gather_directory_files(directory: str) -> List[str]:
    collected: List[str] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]  # prune hidden directories
        for filename in sorted(files):
            if filename.startswith('.'):  # skip hidden files
                continue
            collected.append(os.path.join(root, filename))
            if len(collected) >= MAX_FILES_PER_DIRECTORY:
                return collected
    return collected


def resolve_tagged_file_parts(project_id: str, payload: Dict[str, Any]) -> FileTagResolution:
    file_specs = payload.get('file_tags') or []
    if not isinstance(file_specs, list) or not file_specs:
        return FileTagResolution(parts=[], attachments=[], warnings=[], errors=[])

    parts: List[Any] = []
    text_blocks: List[str] = []
    attachments: List[AttachmentMetadata] = []
    warnings: List[str] = []
    errors: List[str] = []
    total_bytes = 0

    assets_dir = _ensure_assets_dir(project_id)

    absolute_files: List[str] = []

    for spec in file_specs:
        if not isinstance(spec, dict):
            continue
        relative_path = str(spec.get('relative_path', '')).strip()
        if not relative_path:
            continue

        try:
            absolute_path = _resolve_asset_path(project_id, relative_path)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Failed to resolve '{relative_path}': {exc}")
            continue

        if not os.path.exists(absolute_path):
            errors.append(f"Attachment '{relative_path}' no longer exists on disk.")
            continue

        if os.path.isdir(absolute_path):
            absolute_files.append(absolute_path)
            attachments.append(AttachmentMetadata(
                relative_path=relative_path.rstrip('/'),
                is_directory=True,
                size_bytes=0,
                mime_type=None,
            ))
            files_in_dir = _gather_directory_files(absolute_path)
            if len(files_in_dir) >= MAX_FILES_PER_DIRECTORY:
                warnings.append(
                    f"Directory '{relative_path}' truncated to the first {MAX_FILES_PER_DIRECTORY} files."
                )
            for child_path in files_in_dir:
                rel_child = os.path.relpath(child_path, assets_dir).replace(os.sep, '/')
                mime_type, _ = mimetypes.guess_type(child_path)
                size_bytes = os.path.getsize(child_path)
                if size_bytes > MAX_SINGLE_FILE_BYTES:
                    warnings.append(f"Skipped '{rel_child}' (>{MAX_SINGLE_FILE_BYTES // (1024 * 1024)}MB)")
                    continue
                if total_bytes + size_bytes > MAX_TOTAL_ATTACHMENT_BYTES:
                    warnings.append("Attachment size limit reached; remaining files skipped.")
                    break

                if _is_text_file(child_path, mime_type):
                    content, truncated = _read_text_file(child_path)
                    header = f"--- {rel_child} ---"
                    if truncated:
                        header = f"{header}\n[truncated to {MAX_TEXT_CHARACTERS} characters]"
                    text_blocks.append(f"{header}\n\n{content}\n")
                    parts.append(_make_text_part(header, content))
                elif _is_image_file(mime_type):
                    with open(child_path, 'rb') as handle:
                        binary_data = handle.read()
                    parts.append(_make_image_part(rel_child, mime_type or 'application/octet-stream', binary_data))
                else:
                    warnings.append(f"Skipped '{rel_child}' (unsupported file type).")
                    continue

                attachments.append(AttachmentMetadata(
                    relative_path=rel_child,
                    is_directory=False,
                    size_bytes=size_bytes,
                    mime_type=mime_type,
                ))
                total_bytes += size_bytes
            continue

        mime_type, _ = mimetypes.guess_type(absolute_path)
        size_bytes = os.path.getsize(absolute_path)
        if size_bytes > MAX_SINGLE_FILE_BYTES:
            warnings.append(f"Skipped '{relative_path}' (>{MAX_SINGLE_FILE_BYTES // (1024 * 1024)}MB)")
            continue
        if total_bytes + size_bytes > MAX_TOTAL_ATTACHMENT_BYTES:
            warnings.append("Attachment size limit reached; remaining files skipped.")
            break

        rel_file = os.path.relpath(absolute_path, assets_dir).replace(os.sep, '/')
        if _is_text_file(absolute_path, mime_type):
            content, truncated = _read_text_file(absolute_path)
            header = f"--- {rel_file} ---"
            if truncated:
                header = f"{header}\n[truncated to {MAX_TEXT_CHARACTERS} characters]"
            text_blocks.append(f"{header}\n\n{content}\n")
            parts.append(_make_text_part(header, content))
        elif _is_image_file(mime_type):
            with open(absolute_path, 'rb') as handle:
                binary_data = handle.read()
            parts.append(_make_image_part(rel_file, mime_type or 'application/octet-stream', binary_data))
        else:
            warnings.append(f"Skipped '{relative_path}' (unsupported file type).")
            continue

        attachments.append(AttachmentMetadata(
            relative_path=rel_file,
            is_directory=False,
            size_bytes=size_bytes,
            mime_type=mime_type,
        ))
        absolute_files.append(absolute_path)
        total_bytes += size_bytes

    return FileTagResolution(
        parts=parts,
        text_blocks=text_blocks,
        attachments=attachments,
        warnings=warnings,
        errors=errors,
        absolute_files=absolute_files,
    )
