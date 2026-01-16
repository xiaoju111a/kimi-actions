FROM python:3.12-slim

WORKDIR /app

# Cache bust - update this to force rebuild
ARG CACHE_BUST=20260117_v1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for building kimi-sdk and kimi-agent-sdk
RUN pip install --no-cache-dir uv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install semgrep for security scanning (optional, will skip if not available)
RUN pip install --no-cache-dir semgrep || echo "Semgrep installation skipped"

# Configure git for agent operations
RUN git config --global user.name "Kimi Bot" && \
    git config --global user.email "kimi@moonshot.cn"

COPY src/ ./src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
