# syntax=docker/dockerfile:1

# Image for deploying the office hours queue to Google Cloud Run, like seating's
# and sections'.

# ---------------------------------------------------------------------------
# Frontend
#
# Builds the React app (src/) with Vite into oh_queue/static/dist, which the
# runtime stage copies. Node isn't in the shipped image.
# ---------------------------------------------------------------------------
FROM node:24-slim AS frontend

WORKDIR /build
# Copied on their own so the packages are only reinstalled when they change.
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY tsconfig.json vite.config.ts ./
COPY src ./src
RUN yarn typecheck && yarn build

# ---------------------------------------------------------------------------
# Build stage
#
# Installs the Python dependencies into a venv that is copied into the runtime
# stage, so pip and its build cache stay out of the shipped image.
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied on its own so the dependency layer is only rebuilt when the pins change.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.14-slim

RUN useradd --create-home --uid 1000 app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=. \
    FLASK_APP=manage.py \
    PORT=8080

WORKDIR /app
COPY . .
COPY --from=frontend /build/oh_queue/static/dist ./oh_queue/static/dist

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.environ.get("PORT", "8080") + "/health")'

# With RUN_MIGRATIONS=true (set on staging and production, never on PR previews,
# which share the staging database), apply database migrations before starting.
# `exec` keeps gunicorn as PID 1 so it gets SIGTERM directly on redeploy.
# One worker process with threads, as in seating and sections: Cloud Run's
# default instance is 1 vCPU, and the page polls the server, so requests are
# short and I/O-bound. Override WEB_CONCURRENCY / GUNICORN_THREADS to tune.
CMD ["sh", "-c", "if [ \"$RUN_MIGRATIONS\" = true ]; then flask db upgrade || exit 1; fi; exec gunicorn -b 0.0.0.0:${PORT:-8080} manage:app --workers ${WEB_CONCURRENCY:-1} --threads ${GUNICORN_THREADS:-8} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile -"]
