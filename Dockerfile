# ---- Base Stage ----
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

# ---- Builder Stage ----
FROM base AS builder

# --build-arg
ARG PIP_INDEX_URL=https://pypi.org/simple

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY core/requirements.txt .
RUN pip install -i $PIP_INDEX_URL --no-cache-dir -r requirements.txt

# ---- Frontend Builder Stage ----
FROM node:lts-slim AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/yarn.lock* frontend/package-lock.json* ./frontend/

WORKDIR /app/frontend
RUN npm install

COPY frontend/ .

RUN npm run build

# ---- Final Stage ----
FROM base AS final

ARG TARGETARCH
ENV NODE_VERSION=22.17.0

RUN apt-get update && apt-get install -y curl xz-utils && \
    case ${TARGETARCH} in \
        "amd64") ARCH="x64" ;; \
        "arm64") ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-${ARCH}.tar.xz" \
    | tar -xJf - -C /usr/local --strip-components=1 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get purge -y --auto-remove curl xz-utils && \
    ln -sf /usr/local/bin/node /usr/bin/node && \
    ln -sf /usr/local/bin/npm /usr/bin/npm && \
    ln -sf /usr/local/bin/npx /usr/bin/npx && \
    node -v && npm -v && npx -v

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=frontend-builder /app/frontend/out /app/frontend/out

COPY core/ .

RUN mkdir -p workspace projects && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "run_server.py", "--host", "0.0.0.0", "--port", "8000"]