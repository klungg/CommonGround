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
	$(MAKE) api-run

frontend: bridge
	$(MAKE) frontend-run

dev: bridge
	@echo "Bridge is running in the background."
	@echo "Run 'make api' and 'make frontend' (or use 'make start')."

api-run:
	cd core && \
	if [ ! -d .venv ]; then \
		uv venv; \
	fi; \
	uv sync && \
	uv run run_server.py --reload

frontend-run:
	cd frontend && npm install && npm run dev

start: bridge
	@echo "Bridge is healthy; starting API and frontend after short delay."; \
	set -e; \
	API_PID=""; \
	FE_PID=""; \
	cleanup() { \
		if [ -n "$$API_PID" ]; then \
			kill -TERM -$$API_PID 2>/dev/null || true; \
			API_PID=""; \
		fi; \
		if [ -n "$$FE_PID" ]; then \
			kill -TERM -$$FE_PID 2>/dev/null || true; \
			FE_PID=""; \
		fi; \
	}; \
	trap 'cleanup' EXIT; \
	trap 'cleanup; exit 130' INT TERM; \
	sleep 3; \
	( \
		set -e; \
		cd core; \
		if [ ! -d .venv ]; then \
			echo "[api] Creating Python venv with uv"; \
			uv venv; \
		fi; \
		echo "[api] Syncing dependencies with uv"; \
		uv sync; \
		echo "[api] Starting FastAPI dev server"; \
		uv run run_server.py --reload \
	) & \
	API_PID=$$!; \
	sleep 3; \
	( \
		set -e; \
		cd frontend; \
		echo "[frontend] Installing npm dependencies"; \
		npm install; \
		echo "[frontend] Starting Next.js dev server"; \
		npm run dev \
	) & \
	FE_PID=$$!; \
	wait $$API_PID $$FE_PID
