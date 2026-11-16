# Multi-arch (amd64 + arm64): every dependency ships wheels for both.
FROM python:3.12-slim-trixie

RUN pip install --no-cache-dir uv==0.13.7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    ORIGEN_DATA_DIR=/app/data \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# The data files first, in their own layer: fetched from their publishers and checked
# against the SHA-256s pinned in data.py (standard library only), so code changes never
# download them again. They never enter git.
COPY src/origen/data.py /tmp/fetch_data.py
RUN python /tmp/fetch_data.py /app/data && rm /tmp/fetch_data.py

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project

COPY schemas ./schemas
COPY src ./src
RUN uv sync --frozen --no-dev \
    && origen check-data \
    && chmod -R a+rX /app \
    && useradd --system --uid 10001 --home /app app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["origen", "serve", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
