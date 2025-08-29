# GPT PR Review Bot

A GitHub PR reviewer powered by GPT. Backend is FastAPI; CI and PR hooks run on GitHub Actions. Dependencies & container builds use **uv**.

## Quickstart
```bash
uv sync
uv run fastapi dev app/main.py
# http://127.0.0.1:8000/healthz

## Automated PR Review (Step 2)
- On each PR, the workflow calls `app/cli_review.py`.
- It fetches changed files, truncates large patches, asks GPT for feedback, and posts a comment.

### Local dry run
```bash
# copy .env.example -> .env and fill OPENAI_API_KEY
export GITHUB_TOKEN=ghp_xxx       # a classic token with repo access (for local only)
export GITHUB_REPOSITORY=RunicWolf/gpt-pr-review-bot
export PULL_REQUEST_NUMBER=1
uv run python app/cli_review.py
