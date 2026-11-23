# syntax=docker/dockerfile:1

# Image for deploying the office hours queue to Google Cloud Run, like seating's
# and sections'.

# ---------------------------------------------------------------------------
# Node packages
#
# Babel, which compiles the React components into one script in the build stage.
# ---------------------------------------------------------------------------
FROM node:24-slim AS node

WORKDIR /build
COPY package.json yarn.lock ./
# Babel is in dependencies; devDependencies only has Flow, which the build doesn't use.
RUN yarn install --frozen-lockfile --production

# ---------------------------------------------------------------------------
# Build stage
#
# Installs the Python dependencies into a venv that is copied into the runtime
# stage, so pip and its build cache stay out of the shipped image, then builds
# the frontend: in production the app serves oh_queue/static/public/common.js
# and style.css as they are (oh_queue/assets.py), so `flask build` makes them
# here, with Node, which the runtime image doesn't need.
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied on its own so the dependency layer is only rebuilt when the pins change.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /build
COPY --from=node /build/node_modules ./node_modules
COPY . .
# `flask build` refuses to run in production, and in development needs no
# settings: it renders the queue page once, which compiles the bundles.
RUN ENV=dev FLASK_APP=manage.py PYTHONPATH=. flask build

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
# Owned by the app user: webassets writes its cache in oh_queue/static.
COPY --chown=app:app . .
COPY --from=builder --chown=app:app /build/oh_queue/static/public ./oh_queue/static/public

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
