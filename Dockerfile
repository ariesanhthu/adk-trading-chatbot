# Multi-stage build cho FastAPI + ADK với uv
FROM python:3.13-slim as builder

WORKDIR /build

# Cài build dependencies và curl (để cài uv)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài uv (package manager nhanh cho Python)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy dependency files (cần cả uv.lock để đảm bảo versions chính xác)
COPY pyproject.toml uv.lock ./

# Sync dependencies với uv (tạo .venv và cài tất cả packages)
# --frozen: dùng chính xác versions từ uv.lock, không update
RUN uv sync --frozen

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment từ builder
# uv sync tạo .venv trong /build/.venv, copy sang /app/.venv
COPY --from=builder /build/.venv /app/.venv

# Set PATH để dùng Python và packages từ venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY app/ ./app/
COPY agents/ ./agents/
COPY configs/ ./configs/
COPY utils/ ./utils/
COPY tools/ ./tools/
COPY run_server.py ./
COPY pyproject.toml ./

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8002/health', timeout=5)" || exit 1

# Run FastAPI server
# FastAPI sẽ tự động load ADK agent từ agents/root_agent khi import
CMD ["python", "run_server.py"]

