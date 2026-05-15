# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install build dependencies (needed for some compiled extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtual environment in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# Runtime system libraries only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from builder — no compiler needed at runtime
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user and working directory
RUN groupadd --gid 1001 aegis \
 && useradd --uid 1001 --gid aegis --shell /bin/bash --create-home aegis

WORKDIR /app

# Copy application source
COPY --chown=aegis:aegis . .

USER aegis

EXPOSE 8000

# 4 uvicorn workers are a reasonable default for the container CPU allocation;
# override via UVICORN_WORKERS env var if needed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
