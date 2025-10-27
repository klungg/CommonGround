import logging
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

from .pdf_agent_service import PdfAgentConfig, run_pdf_to_markdown

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pdf", tags=["pdf-agent"])


@router.post("/to-markdown")
async def pdf_to_markdown(file: UploadFile = File(...)) -> Dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "document.pdf"

    try:
        result = await run_pdf_to_markdown(pdf_bytes=pdf_bytes, filename=filename, config=PdfAgentConfig())
    except ValueError as validation_exc:
        raise HTTPException(status_code=413, detail=str(validation_exc)) from validation_exc
    except Exception as err:  # pragma: no cover - defensive
        logger.exception("pdf_agent_processing_failed", extra={"file_name": filename})
        raise HTTPException(status_code=500, detail="Failed to process PDF.") from err

    safe_result = {
        key: value
        for key, value in result.items()
        if key not in {"step1_raw_response", "step2_raw_response"}
    }

    return {"status": "success", "data": safe_result}
