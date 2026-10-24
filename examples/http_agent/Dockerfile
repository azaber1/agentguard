FROM python:3.13-slim
RUN pip install --no-cache-dir "fastapi>=0.115,<1.0" "uvicorn>=0.30"
WORKDIR /app
COPY server.py .
RUN useradd --system --uid 10001 agent
USER agent
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
