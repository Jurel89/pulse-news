FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.app.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
RUN npm ci
RUN npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PULSE_NEWS_DATA_DIR=/data

WORKDIR /app

RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

COPY backend ./backend
COPY alembic.ini ./
COPY alembic/ ./alembic/
RUN pip install --no-cache-dir ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
