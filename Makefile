.PHONY: bridge api frontend dev start api-run frontend-run proxy

# Proxy configuration
# Use with: `make start proxy`  or  `make start PROXY=1 [PROXY_URL=http://localhost:8001]`
PROXY ?= 0
PROXY_URL ?=
PROXY_NO_PROXY ?= localhost,127.0.0.1,::1

# Enable proxy mode if the special goal `proxy` is present
ifneq (,$(filter proxy,$(MAKECMDGOALS)))
  PROXY := 1
endif

# When enabled, export proxy variables for commands run in this Make process
ifeq ($(strip $(PROXY)),1)
  ifeq ($(strip $(PROXY_URL)),)
    PROXY_URL := http://localhost:8001
  endif
  export HTTPS_PROXY := $(PROXY_URL)
  export HTTP_PROXY := $(PROXY_URL)
  export NO_PROXY := $(PROXY_NO_PROXY)
endif

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
        -e 'do script "cd \"$(CURDIR)/core\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY); fi; if [ ! -d .venv ]; then uv venv; fi; uv sync && uv run run_server.py --reload --log-level DEBUG"' \
		-e 'end tell'

frontend: bridge
	@echo "Launching frontend in a new Terminal window with debug logging..."
	@osascript -e 'tell application "Terminal"' \
		-e 'activate' \
        -e 'do script "cd \"$(CURDIR)/frontend\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY); fi; npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug npm run dev"' \
		-e 'end tell'

dev: bridge
	@echo "Bridge is running in the background."
	@echo "Run 'make api' and 'make frontend' (or use 'make start')."

api-run:
	cd core && \
	if [ ! -d .venv ]; then \
		uv venv; \
	fi; \
	if [ "$(PROXY)" = "1" ]; then \
		HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" uv sync; \
	else \
		uv sync; \
	fi; \
	if [ "$(PROXY)" = "1" ]; then \
		HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" uv run run_server.py --reload --log-level DEBUG; \
	else \
		uv run run_server.py --reload --log-level DEBUG; \
	fi

frontend-run:
	cd frontend && \
	if [ "$(PROXY)" = "1" ]; then \
		HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" npm install; \
	else \
		npm install; \
	fi && \
	LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug \
	if [ "$(PROXY)" = "1" ]; then \
		HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" npm run dev; \
	else \
		npm run dev; \
	fi

start:
	@echo "Pre-binding port 8000 on IPv4 and IPv6..."; \
	python3 -m http.server 8000 --bind 127.0.0.1 >/dev/null 2>&1 & PREBIND4=$$!; echo $$PREBIND4 > /tmp/prebind4.pid; \
	python3 -m http.server 8000 --bind ::1       >/dev/null 2>&1 & PREBIND6=$$!; echo $$PREBIND6 > /tmp/prebind6.pid || true; \
	echo "Launching HTTP Toolkit..."; \
	open -a "HTTP Toolkit"; \
	sleep 2; \
	echo "Releasing pre-bind on port 8000..."; \
	if [ -f /tmp/prebind4.pid ]; then kill $$(cat /tmp/prebind4.pid) 2>/dev/null || true; rm -f /tmp/prebind4.pid; fi; \
	if [ -f /tmp/prebind6.pid ]; then kill $$(cat /tmp/prebind6.pid) 2>/dev/null || true; rm -f /tmp/prebind6.pid; fi; \
	echo "Starting bridge..."; \
	$(MAKE) bridge || exit $$?; \
	echo "Bridge is healthy; launching API and frontend terminals with debug logging."; \
	osascript -e 'tell application "Terminal"' \
		-e 'activate' \
		-e 'do script "cd \"$(CURDIR)/core\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY); fi; if [ ! -d .venv ]; then uv venv; fi; uv sync && uv run run_server.py --reload --log-level DEBUG"' \
		-e 'end tell'; \
	sleep 2; \
	osascript -e 'tell application "Terminal"' \
		-e 'activate' \
		-e 'do script "cd \"$(CURDIR)/frontend\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY); fi; npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug npm run dev"' \
		-e 'end tell'

proxy:
	@true
