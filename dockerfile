FROM python:3.12-slim

# Install uv binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project
WORKDIR /app
COPY . /app

# Install deps into a project venv using the lockfile
RUN uv sync --frozen --no-cache

# Run the app via the FastAPI CLI (serves with uvicorn)
CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--port", "80", "--host", "0.0.0.0"]
