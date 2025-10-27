# Repository Guidelines

## Project Structure & Architecture
Common Ground spans `core/` (FastAPI agent runtime), `frontend/` (Next.js UI), and `deployment/` (Docker orchestration plus the Gemini bridge). Engine code sits in `core/agent_core/`, API routers in `core/api/`, and agent profiles in `core/agent_profiles/`; shared media lives in `assets/`. Consult `docs/architecture.md` for the layered component map and directory responsibilities.

## Agent Runtime & Collaboration Flow
Every agent runs on the reusable `AgentNode` loop, with YAML profiles defining Partner, Principal, and Associate behavior. Work Modules in `team_state` capture scope and status as agents coordinate through dispatcher tools and the inbox. See `docs/framework/01-agent-runtime.md` for the Turn lifecycle and `docs/framework/02-team-collaboration.md` for role handoffs and parent-child links.

## Build, Test, & Development Commands
- `cd core && uv venv && uv sync` — provision Python 3.12 env and deps.
- `cd core && cp env.sample .env && uv run run_server.py --reload` — start API on http://localhost:8000.
- `cd frontend && npm install && npm run dev` — serve the UI at http://localhost:3000.
- `cd deployment && git submodule update --init --recursive && docker compose up` — boot the full stack, including the Gemini bridge needed for local LLM calls.

## Coding Style, Tooling, & Naming
Follow PEP 8 with four-space indents, typed functions, and snake_case modules in `core/`; keep reusable logic in `services/` or `framework/`. Frontend files use PascalCase components, camelCase hooks, and utility-first styling. When adding tools, inherit from `BaseToolNode` and register via `@tool_registry` (see `docs/guides/02-developing-tools.md`); `docs/guides/06-built-in-tools.md` lists existing toolsets and parameters.

## Testing & Observability
Backend tests live in `core/tests/` and run with `uv run pytest`; focus on new agent flows and API contracts. Frontend specs go under `frontend/__tests__/` with `.test.tsx` suffixes, and note manual QA when tests lag. Enable `STATE_DUMP=true` or `CAPTURE_LLM_REQUEST_BODY=true` as outlined in `docs/guides/04-debugging.md` to inspect RunContext snapshots and raw LLM payloads.

## Commit & Pull Request Guidelines
Use Conventional Commits (`feat:`, `fix:`, `docs:`) with scoped changes; no generated artifacts. Pull requests need a concise summary, linked issues, environment or migration callouts, and screenshots or agent logs when behavior shifts. Verify API, UI, and Docker targets before requesting review.

## Docs Reference Map
- `docs/architecture.md` — architecture overview, state flow diagrams, directory map.
- `docs/framework/03-api-reference.md` — PocketFlow tool schemas and service contracts.
- `docs/guides/01-agent-profiles.md` — editing agent personas and flow deciders.
- `docs/guides/03-advanced-customization.md` — extending observers, protocols, persistence.
- `docs/guides/05-llm-providers.md` — configuring LiteLLM adapters, env keys, model overrides.

## Non-Obvious Gotchas & Learnings
- **Next.js base path:** `next.config.ts` sets `basePath: '/webview'`, so every app route—including the new PDF API proxy—lives under `/webview`. Client-side fetches must hit `/webview/api/...`; the PDF page now defaults to that path, but other tooling may still need the prefix.
- **Gemini bridge auth:** The repo relies on the Dockerised Gemini CLI bridge and its OAuth state. Many configs (e.g., `core/agent_profiles/llm_configs/*`) still show placeholder API keys like `5678`, but real calls succeed because the OpenAI-compatible endpoint at `${GEMINI_BRIDGE_URL}/v1` handles auth transparently. When wiring new services, reuse that base URL instead of expecting an API key.
- **PDF agent flow:** `core/api/pdf_agent_service.py` runs two sequential Gemini calls—first extraction, then formatting—without truncating the draft or enforcing a per-request timeout.
