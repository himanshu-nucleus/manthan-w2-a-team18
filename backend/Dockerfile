# syntax=docker/dockerfile:1

# AI Manthan backend - FastAPI on Python 3.13.
# Multi-stage: wheels are built in `builder`, so no build toolchain ships in the
# final image. psycopg[binary] is a wheel and needs no compiler.

FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dependencies first so the layer is cached until requirements.txt changes.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# curl is needed by HEALTHCHECK only; it is a few hundred KB and keeps the
# healthcheck independent of the Python environment.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user.
RUN groupadd --system --gid 1001 manthan \
    && useradd --system --uid 1001 --gid manthan --create-home manthan

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN python -m pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Source last: code changes do not invalidate the dependency layers.
COPY --chown=manthan:manthan app ./app
RUN mkdir -p /app/uploads && chown manthan:manthan /app/uploads

USER manthan

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
