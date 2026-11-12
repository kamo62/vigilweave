FROM oven/bun:1.3.10 AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/bun.lock* ./
RUN bun install
COPY frontend/ ./
RUN bun run build

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./main.py
COPY README.md ./README.md
COPY --from=frontend-build /app/static ./static

ENV DATABASE_URL=sqlite:///./license_server.db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
