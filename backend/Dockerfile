FROM python:3.13-slim AS base
RUN pip install --no-cache-dir uv==0.11.32
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && useradd --system --uid 10001 agentguard
USER agentguard

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
ENTRYPOINT ["./docker-entrypoint.sh"]
