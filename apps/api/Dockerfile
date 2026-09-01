# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PORT=8080

# Non-root: the runtime never writes to the image.
RUN useradd --create-home --uid 10001 app

WORKDIR /app

# No dependency install step yet — the service is stdlib-only. When that
# changes, install requirements above this COPY so the layer caches
# independently of the source.
COPY src/ ./src/

USER app
EXPOSE 8080
CMD ["python", "-m", "api.main"]
