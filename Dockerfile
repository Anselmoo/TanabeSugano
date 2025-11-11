# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy application code first
COPY . .

# Install dependencies with uv
RUN uv sync --frozen --no-cache

# Set environment variables for PATH to include venv bin
ENV PATH="/app/.venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Run the application
CMD ["uv", "run", "tanabesugano"]
