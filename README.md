# GPT PR Review Bot

A GitHub PR reviewer powered by GPT. Backend is FastAPI; CI and PR hooks run on GitHub Actions. Dependencies & container builds use **uv**.

## Quickstart
```bash
uv sync
uv run fastapi dev app/main.py
# http://127.0.0.1:8000/healthz
