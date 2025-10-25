.PHONY: bridge api frontend dev start api-run frontend-run

bridge:
	cd deployment && \
	docker compose up --build --detach bridge && \
	echo "Waiting for bridge container to report healthy (timeout 120s)..." && \
	MAX_WAIT=120; \
	while [ $$MAX_WAIT -gt 0 ]; do \
		CONTAINER=$$(docker compose ps --format '{{.Name}}' bridge | head -n1); \
		if [ -z "$$CONTAINER" ]; then \
			sleep 2; \
			MAX_WAIT=$$((MAX_WAIT-2)); \
			continue; \
		fi; \
		STATUS=$$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $$CONTAINER); \
		if [ "$$STATUS" = "healthy" ]; then \
			echo "Bridge container $$CONTAINER is healthy."; \
			exit 0; \
		fi; \
		if [ "$$STATUS" = "exited" ]; then \
			echo "Bridge container $$CONTAINER exited unexpectedly."; \
			docker compose logs bridge; \
			exit 1; \
		fi; \
		sleep 2; \
		MAX_WAIT=$$((MAX_WAIT-2)); \
	done; \
	echo "Timed out waiting for bridge health."; \
	docker compose logs bridge; \
	exit 1

api: bridge
	@echo "Launching API server in a new Terminal window with debug logging..."
	@osascript -e 'tell application "Terminal"' \
		-e 'activate' \
		-e 'do script "cd \"$(CURDIR)/core\" && if [ ! -d .venv ]; then uv venv; fi; uv sync && uv run run_server.py --reload --log-level DEBUG"' \
		-e 'end tell'

frontend: bridge
	@echo "Launching frontend in a new Terminal window with debug logging..."
	@osascript -e 'tell application "Terminal"' \
		-e 'activate' \
		-e 'do script "cd \"$(CURDIR)/frontend\" && npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug npm run dev"' \
		-e 'end tell'

dev: bridge
	@echo "Bridge is running in the background."
	@echo "Run 'make api' and 'make frontend' (or use 'make start')."

api-run:
	cd core && \
	if [ ! -d .venv ]; then \
		uv venv; \
	fi; \
	uv sync && \
	uv run run_server.py --reload --log-level DEBUG

frontend-run:
	cd frontend && npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug npm run dev

start: bridge
	@echo "Bridge is healthy; launching API and frontend terminals with debug logging."; \
	osascript -e 'tell application "Terminal"' \
		-e 'activate' \
		-e 'do script "cd \"$(CURDIR)/core\" && if [ ! -d .venv ]; then uv venv; fi; uv sync && uv run run_server.py --reload --log-level DEBUG"' \
		-e 'end tell'; \
	sleep 2; \
	osascript -e 'tell application "Terminal"' \
		-e 'activate' \
		-e 'do script "cd \"$(CURDIR)/frontend\" && npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug npm run dev"' \
		-e 'end tell'
