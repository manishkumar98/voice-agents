# ── Phase 5 — Multi-stage Docker build ────────────────────────────────────────
# Stage 1: builder — install dependencies into a venv
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY voice-agents/requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY voice-agents/ ./voice-agents/

# Environment defaults (override at runtime via .env or Docker secrets)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Streamlit uses 8501 by default
EXPOSE 8501

# Health check — polls Streamlit's /_stcore/health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" \
    || exit 1

# Drop to non-root
USER appuser

# Launch production UI
CMD ["streamlit", "run", "voice-agents/phase5/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
