FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
# Install dependencies first so this layer is cached when only code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH" PORT=8000
EXPOSE 8000
# --proxy-headers: take the client IP from X-Forwarded-For, but only from proxies
# listed in FORWARDED_ALLOW_IPS (needed for per-IP rate limiting behind a host's proxy).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
