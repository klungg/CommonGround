# PDF → Markdown Agent

The PDF agent provides a standalone two-step workflow that leverages Gemini via the bridge to transform a local PDF into clean Markdown without performing any on-host OCR or text extraction.

## Overview

1. **Extraction pass** – the uploaded PDF is sent to Gemini with the prompt _“Please extract the text from the attached PDF.”_ and the raw response is stored as a draft markdown transcript.
2. **Formatting pass** – the same PDF and the draft text are sent back to Gemini with instructions to align the Markdown with the source document’s structure (headings, lists, tables, emphasis).

The agent lives outside the core multi-agent runtime and is exposed through a dedicated API endpoint and a companion web page (`/pdf-to-markdown`).

## Backend entry points

- `core/api/pdf_agent_service.py` – service logic that validates uploads, orchestrates the two Gemini calls, and returns both the intermediate and final Markdown.
- `core/api/pdf_agent.py` – FastAPI router that accepts multipart uploads at `POST /pdf/to-markdown` and exposes the service to clients.

### Configuration

Environment variables can be used to tweak the behaviour without code changes:

```
PDF_AGENT_MODEL_STEP1=openai/gemini-2.5-flash   # first-pass extraction model
PDF_AGENT_MODEL_STEP2=openai/gemini-2.5-pro     # second-pass formatting model
PDF_AGENT_MAX_MB=10                             # max PDF size (MB)
PDF_AGENT_STEP1_SYSTEM_PROMPT=...
PDF_AGENT_STEP2_SYSTEM_PROMPT=...
```

All values are optional; defaults are chosen to balance quality and latency for typical contract or specification PDFs.

## Frontend experience

- `frontend/app/pdf-to-markdown/page.tsx` renders the upload and preview workflow and surfaces both the step-one draft and the final Markdown (with download and copy helpers). By default it targets the `/webview/api/pdf-to-markdown` proxy to match the app’s base path; adjust if you renounce `basePath`.
- `frontend/app/api/pdf-to-markdown/route.ts` proxies uploads from Next.js to the FastAPI endpoint, reusing `NEXT_PUBLIC_API_URL` for the backend base URL.
- When serving the UI behind a custom `basePath` (default `/webview` per `next.config.ts`), ensure `NEXT_PUBLIC_BASE_PATH` matches so client-side requests hit the correct API route.
- `frontend/components/layout/AppSidebar.tsx` contains a new “PDF → Markdown” entry so the tool is accessible without entering the multi-agent chat workspace.

## Testing

`core/tests/test_pdf_agent.py` includes unit coverage for the service (verifying truncation and the dual call) and the HTTP endpoint. The tests stub `litellm.acompletion` to avoid real network usage.

## Operational Notes

- The agent stores uploaded PDFs in a temporary directory per request and automatically cleans up after completion.
- Step-one drafts feed directly into the formatter; no truncation is applied, so extremely large PDFs will push against the Gemini context window if handled in a single pass.
- For debugging, raw LLM responses are available inside the service result but are stripped before returning to clients.
