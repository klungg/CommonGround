# Quick start:
#   make start            # launch bridge, API, frontend (no proxy)
#   make start proxy      # launch stack with HTTP Toolkit proxy (defaults to http://localhost:8001)
#   make rebuild          # rebuild the bridge image (runs without proxy)

#   PROXY_URL=http://host:port make start proxy  # custom proxy endpoint
# Proxy mode rewrites the container proxy host to host.docker.internal automatically; host shells keep the original value.
# To rebuild the bridge image explicitly, run `make rebuild` (runs without proxy).

# Prerequisites:
#   - HTTP Toolkit installed
#   - docker compose (v2) available, Docker daemon running
#   - macOS users: Terminal automation permissions for `osascript` (used by `make start`)
#   - HTTP Toolkit certificate file in root directory

# ------------------------------------------------------------
# Initialize the project
# ------------------------------------------------------------
.PHONY: bridge api frontend dev start api-run frontend-run proxy

# Proxy configuration
# Use with: `make start proxy`  or  `make start PROXY=1 [PROXY_URL=http://localhost:8001]`
PROXY ?= 0
PROXY_URL ?=
PROXY_CA_CERT ?= $(CURDIR)/http-toolkit-ca-certificate.crt
PROXY_NO_PROXY ?= localhost,127.0.0.1,::1,bridge,core,frontend

comma := ,
space :=
space +=

# Enable proxy mode if the special goal `proxy` is present
ifneq (,$(filter proxy,$(MAKECMDGOALS)))
  PROXY := 1
endif

# When enabled, export proxy variables for commands run in this Make process
ifeq ($(strip $(PROXY)),1)
  ifeq ($(strip $(PROXY_URL)),)
    PROXY_URL := http://localhost:8001
  endif
  PROXY_URL_DOCKER := $(PROXY_URL)
  ifneq (,$(findstring ://localhost,$(PROXY_URL_DOCKER)))
    PROXY_URL_DOCKER := $(subst ://localhost,://host.docker.internal,$(PROXY_URL_DOCKER))
  endif
  ifneq (,$(findstring ://127.0.0.1,$(PROXY_URL_DOCKER)))
    PROXY_URL_DOCKER := $(subst ://127.0.0.1,://host.docker.internal,$(PROXY_URL_DOCKER))
  endif
  ifneq (,$(findstring ://0.0.0.0,$(PROXY_URL_DOCKER)))
    PROXY_URL_DOCKER := $(subst ://0.0.0.0,://host.docker.internal,$(PROXY_URL_DOCKER))
  endif
  ifneq ($(strip $(PROXY_URL_DOCKER)),$(strip $(PROXY_URL)))
    $(info Proxy URL rewritten for containers: $(PROXY_URL_DOCKER))
  endif
  export HTTPS_PROXY := $(PROXY_URL)
  export HTTP_PROXY := $(PROXY_URL)
  export NO_PROXY := $(PROXY_NO_PROXY)
  export GLOBAL_AGENT_HTTP_PROXY := $(PROXY_URL)
  export GLOBAL_AGENT_HTTPS_PROXY := $(PROXY_URL)
  export GLOBAL_AGENT_NO_PROXY := $(PROXY_NO_PROXY)
  ifneq ($(strip $(PROXY_CA_CERT)),)
    export REQUESTS_CA_BUNDLE := $(PROXY_CA_CERT)
    export NODE_EXTRA_CA_CERTS := $(PROXY_CA_CERT)
  endif
  PROXY_NO_PROXY_WORDS := $(subst $(comma),$(space),$(PROXY_NO_PROXY))
  PROXY_NO_PROXY_DOCKER_WORDS := $(filter-out host.docker.internal,$(PROXY_NO_PROXY_WORDS))
  PROXY_NO_PROXY_DOCKER := $(subst $(space),$(comma),$(strip $(PROXY_NO_PROXY_DOCKER_WORDS)))
  ifeq ($(strip $(PROXY_NO_PROXY_DOCKER)),)
    PROXY_NO_PROXY_DOCKER := $(PROXY_NO_PROXY)
  endif
  BRIDGE_PROXY_ENV := BRIDGE_HTTP_PROXY="$(PROXY_URL_DOCKER)" BRIDGE_HTTPS_PROXY="$(PROXY_URL_DOCKER)" BRIDGE_NO_PROXY="$(PROXY_NO_PROXY_DOCKER)" BRIDGE_GLOBAL_AGENT_HTTP_PROXY="$(PROXY_URL_DOCKER)" BRIDGE_GLOBAL_AGENT_HTTPS_PROXY="$(PROXY_URL_DOCKER)" BRIDGE_GLOBAL_AGENT_NO_PROXY="$(PROXY_NO_PROXY_DOCKER)"
  CLEAR_PROXY_ENV := HTTP_PROXY= HTTPS_PROXY= NO_PROXY= GLOBAL_AGENT_HTTP_PROXY= GLOBAL_AGENT_HTTPS_PROXY= GLOBAL_AGENT_NO_PROXY=
endif

DOCKER_COMPOSE := docker compose -f docker-compose.yaml
ifeq ($(strip $(PROXY)),1)
  DOCKER_COMPOSE += -f docker-compose.proxy.yaml
endif
DOCKER_COMPOSE_CMD = $(DOCKER_COMPOSE)
ifeq ($(strip $(PROXY)),1)
  DOCKER_COMPOSE_CMD = env $(CLEAR_PROXY_ENV) $(BRIDGE_PROXY_ENV) $(DOCKER_COMPOSE)
endif

bridge:
	cd deployment && \
	$(DOCKER_COMPOSE_CMD) up --detach bridge && \
	echo "Waiting for bridge container to report healthy (timeout 120s)..." && \
	MAX_WAIT=120; \
	while [ $$MAX_WAIT -gt 0 ]; do \
		CONTAINER=$$($(DOCKER_COMPOSE_CMD) ps --format '{{.Name}}' bridge | head -n1); \
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
			$(DOCKER_COMPOSE_CMD) logs bridge; \
			echo "Hint: If the image is outdated, rebuild it with 'PROXY=0 docker compose -f deployment/docker-compose.yaml build bridge' and retry."; \
			exit 1; \
		fi; \
		sleep 2; \
		MAX_WAIT=$$((MAX_WAIT-2)); \
	done; \
	echo "Timed out waiting for bridge health."; \
	$(DOCKER_COMPOSE_CMD) logs bridge; \
	echo "Hint: If the image is outdated, rebuild it with 'PROXY=0 docker compose -f deployment/docker-compose.yaml build bridge' and retry."; \
	exit 1

api: bridge
	@echo "Launching API server in a new Terminal window with debug logging..."
	@osascript -e 'tell application "Terminal"' \
		-e 'activate' \
        -e 'do script "cd \"$(CURDIR)/core\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY) REQUESTS_CA_BUNDLE=$(PROXY_CA_CERT) NODE_EXTRA_CA_CERTS=$(PROXY_CA_CERT) GEMINI_BRIDGE_URL=http://host.docker.internal:8765/v1; fi; if [ ! -d .venv ]; then uv venv; fi; uv sync && uv run run_server.py --reload --log-level DEBUG"' \
		-e 'end tell'

frontend: bridge
	@echo "Launching frontend in a new Terminal window with debug logging..."
	@osascript -e 'tell application "Terminal"' \
		-e 'activate' \
        -e 'do script "cd \"$(CURDIR)/frontend\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY) GLOBAL_AGENT_HTTP_PROXY=$(PROXY_URL) GLOBAL_AGENT_HTTPS_PROXY=$(PROXY_URL) GLOBAL_AGENT_NO_PROXY=$(PROXY_NO_PROXY) NODE_EXTRA_CA_CERTS=$(PROXY_CA_CERT); fi; npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug NODE_OPTIONS=\"--require ./proxy-bootstrap.cjs $$NODE_OPTIONS\" npm run dev"' \
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
		HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" REQUESTS_CA_BUNDLE="$(PROXY_CA_CERT)" NODE_EXTRA_CA_CERTS="$(PROXY_CA_CERT)" GEMINI_BRIDGE_URL="http://host.docker.internal:8765/v1" uv sync; \
	else \
		uv sync; \
	fi; \
	if [ "$(PROXY)" = "1" ]; then \
		HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" REQUESTS_CA_BUNDLE="$(PROXY_CA_CERT)" NODE_EXTRA_CA_CERTS="$(PROXY_CA_CERT)" GEMINI_BRIDGE_URL="http://host.docker.internal:8765/v1" uv run run_server.py --reload --log-level DEBUG; \
	else \
		uv run run_server.py --reload --log-level DEBUG; \
	fi

frontend-run:
	cd frontend && \
    if [ "$(PROXY)" = "1" ]; then \
        HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" GLOBAL_AGENT_HTTP_PROXY="$(PROXY_URL)" GLOBAL_AGENT_HTTPS_PROXY="$(PROXY_URL)" GLOBAL_AGENT_NO_PROXY="$(PROXY_NO_PROXY)" NODE_EXTRA_CA_CERTS="$(PROXY_CA_CERT)" NODE_OPTIONS="--require ./proxy-bootstrap.cjs $$NODE_OPTIONS" npm install; \
	else \
		npm install; \
	fi && \
	LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug \
    if [ "$(PROXY)" = "1" ]; then \
        HTTPS_PROXY="$(PROXY_URL)" HTTP_PROXY="$(PROXY_URL)" NO_PROXY="$(PROXY_NO_PROXY)" GLOBAL_AGENT_HTTP_PROXY="$(PROXY_URL)" GLOBAL_AGENT_HTTPS_PROXY="$(PROXY_URL)" GLOBAL_AGENT_NO_PROXY="$(PROXY_NO_PROXY)" NODE_EXTRA_CA_CERTS="$(PROXY_CA_CERT)" NODE_OPTIONS="--require ./proxy-bootstrap.cjs $$NODE_OPTIONS" npm run dev; \
	else \
		npm run dev; \
	fi

start:
	@if [ "$(PROXY)" = "1" ] && [ ! -f "$(PROXY_CA_CERT)" ]; then \
		echo "Proxy certificate not found at $(PROXY_CA_CERT). Update PROXY_CA_CERT or place the file before retrying."; \
		exit 1; \
	fi; \
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
	$(MAKE) PROXY=$(PROXY) PROXY_URL="$(PROXY_URL)" PROXY_CA_CERT="$(PROXY_CA_CERT)" PROXY_NO_PROXY="$(PROXY_NO_PROXY)" bridge || exit $$?; \
	echo "Bridge is healthy; launching API and frontend terminals with debug logging."; \
		osascript -e 'tell application "Terminal"' \
			-e 'activate' \
			-e 'do script "cd \"$(CURDIR)/core\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY) REQUESTS_CA_BUNDLE=$(PROXY_CA_CERT) NODE_EXTRA_CA_CERTS=$(PROXY_CA_CERT) GEMINI_BRIDGE_URL=http://host.docker.internal:8765/v1; fi; if [ ! -d .venv ]; then uv venv; fi; uv sync && uv run run_server.py --reload --log-level DEBUG"' \
			-e 'end tell'; \
	sleep 2; \
	osascript -e 'tell application "Terminal"' \
		-e 'activate' \
        -e 'do script "cd \"$(CURDIR)/frontend\" && if [ \"$(PROXY)\" = \"1\" ]; then export HTTPS_PROXY=$(PROXY_URL) HTTP_PROXY=$(PROXY_URL) NO_PROXY=$(PROXY_NO_PROXY) GLOBAL_AGENT_HTTP_PROXY=$(PROXY_URL) GLOBAL_AGENT_HTTPS_PROXY=$(PROXY_URL) GLOBAL_AGENT_NO_PROXY=$(PROXY_NO_PROXY) NODE_EXTRA_CA_CERTS=$(PROXY_CA_CERT); fi; npm install && LOG_LEVEL=debug NEXT_PUBLIC_LOG_LEVEL=debug NODE_OPTIONS=\"--require ./proxy-bootstrap.cjs $$NODE_OPTIONS\" npm run dev"' \
		-e 'end tell'

proxy:
	@true

# ------------------------------------------------------------
# Rebuild the bridge image
# ------------------------------------------------------------
.PHONY: rebuild

rebuild:
	cd deployment && \
	docker compose -f docker-compose.yaml build bridge
