import base64
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import aiohttp

logger = logging.getLogger(__name__)


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass
class PdfAgentConfig:
    step1_model: str = _env("PDF_AGENT_MODEL_STEP1", "openai/gemini-2.5-flash")
    step2_model: str = _env("PDF_AGENT_MODEL_STEP2", "openai/gemini-2.5-pro")
    max_file_mb: int = int(_env("PDF_AGENT_MAX_MB", "10"))
    bridge_base_url: str = _env(
        "PDF_AGENT_BASE_URL",
        _env("GEMINI_BRIDGE_URL", _env("DEFAULT_BASE_URL", "http://127.0.0.1:8765/v1")),
    )
    api_key: str | None = os.getenv("PDF_AGENT_API_KEY") or os.getenv("DEFAULT_API_KEY")
    step1_system_prompt: str = _env(
        "PDF_AGENT_STEP1_SYSTEM_PROMPT",
        "The assistant is in a meticulous mood.",
    )
    step1_user_prompt: str = _env(
        "PDF_AGENT_STEP1_USER_PROMPT",
        "Please extract the text from the attached PDF.",
    )
    step2_system_prompt: str = _env(
        "PDF_AGENT_STEP2_SYSTEM_PROMPT",
        "The assistant is in a meticulous mood.",
    )
    step2_user_prompt: str = _env(
        "PDF_AGENT_STEP2_USER_PROMPT",
        "The text in the attached text is now in a hard-wrapped OCR format. Please reformat it into proper markdown that mirrors the source layout.",
    )
    step2_text_prefix: str = _env("PDF_AGENT_STEP2_TEXT_PREFIX", "Draft Markdown to refine:\n\n")


def _build_pdf_data_url(pdf_bytes: bytes) -> str:
    base64_data = base64.b64encode(pdf_bytes).decode("utf-8")
    return f"data:application/pdf;base64,{base64_data}"


def _extract_text_from_response(response: Dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        gathered: List[str] = []
        for part in content:
            if isinstance(part, dict):
                text_val = part.get("text") or part.get("content") or part.get("output_text")
                if text_val:
                    gathered.append(str(text_val))
        return "".join(gathered)
    return ""


async def _call_bridge_completion(
    *,
    model: str,
    system_prompt: str,
    content_parts: Any,
    config: PdfAgentConfig,
) -> Dict[str, Any]:
    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": content_parts})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    endpoint = config.bridge_base_url.rstrip("/") + "/chat/completions"

    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, json=payload, headers=headers) as response:
            body = await response.text()
            if response.status >= 400:
                logger.error(
                    "pdf_agent_bridge_error",
                    extra={
                        "model": model,
                        "status": response.status,
                        "body_preview": body[:500],
                    },
                )
                raise RuntimeError(
                    f"Gemini bridge request failed with status {response.status}: {body[:200]}"
                )
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                logger.error(
                    "pdf_agent_bridge_json_error",
                    extra={"model": model, "raw_body_preview": body[:500]},
                    exc_info=True,
                )
                raise RuntimeError("Gemini bridge returned invalid JSON") from exc


async def _run_bridge_call(
    model: str,
    system_prompt: str,
    content_parts: Any,
    config: PdfAgentConfig,
) -> Tuple[str, Dict[str, Any]]:
    logger.info("pdf_agent_llm_call_begin", extra={"model": model})
    response_payload = await _call_bridge_completion(
        model=model,
        system_prompt=system_prompt,
        content_parts=content_parts,
        config=config,
    )
    logger.info("pdf_agent_llm_call_success", extra={"model": model})
    return _extract_text_from_response(response_payload), response_payload


async def run_pdf_to_markdown(
    pdf_bytes: bytes,
    filename: str,
    config: PdfAgentConfig | None = None,
) -> Dict[str, Any]:
    if config is None:
        config = PdfAgentConfig()

    max_bytes = config.max_file_mb * 1024 * 1024
    if len(pdf_bytes) > max_bytes:
        raise ValueError(f"PDF exceeds maximum allowed size of {config.max_file_mb} MB")

    temp_dir = tempfile.mkdtemp(prefix="pdf_agent_")
    step1_response: Dict[str, Any] | None = None
    step2_response: Dict[str, Any] | None = None
    try:
        pdf_path = os.path.join(temp_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        pdf_data_url = _build_pdf_data_url(pdf_bytes)

        step1_parts = [
            {"type": "text", "text": config.step1_user_prompt},
            {"type": "image_url", "image_url": {"url": pdf_data_url}},
        ]

        step1_text, step1_response = await _run_bridge_call(
            model=config.step1_model,
            system_prompt=config.step1_system_prompt,
            content_parts=step1_parts,
            config=config,
        )

        draft_markdown = step1_text.strip()

        step2_text_payload = (
            f"{config.step2_text_prefix}{draft_markdown}" if draft_markdown else config.step2_text_prefix
        )
        step2_parts = [
            {"type": "text", "text": config.step2_user_prompt},
            {"type": "text", "text": step2_text_payload},
            {"type": "image_url", "image_url": {"url": pdf_data_url}},
        ]

        final_markdown, step2_response = await _run_bridge_call(
            model=config.step2_model,
            system_prompt=config.step2_system_prompt,
            content_parts=step2_parts,
            config=config,
        )

        return {
            "file_name": filename,
            "draft_markdown": draft_markdown,
            "final_markdown": final_markdown.strip(),
            "step1_model": config.step1_model,
            "step2_model": config.step2_model,
            "step1_raw_response": step1_response,
            "step2_raw_response": step2_response,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
