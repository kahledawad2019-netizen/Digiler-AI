# Digiler AI backend. Build context = repository root (so the ala platform installs).
#   docker build -f backend/Dockerfile -t digiler-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 HF_HUB_OFFLINE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# 1) the ala platform (retrieval/graphrag/agents/…) + 2) the API deps
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e .
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

# app code + platform config + built knowledge artifacts (mounted in compose too)
COPY config ./config
COPY backend ./backend

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
