# GPT PR Review Bot

A GitHub Action that auto-reviews pull requests using GPT-4o.
It filters and slims diffs, generates a summary, optionally posts **inline comments**, applies **labels** based on severity, and writes a **Job Summary** to the Actions run. You can even **block merges** when the bot thinks changes are required.

![status](https://img.shields.io/badge/PR%20Review-GPT-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Features

- 🔍 Diff filtering: glob includes/excludes + optional ignore file
- ✂️ Context control: per-file truncation + total cap + changed-lines slimming
- 🎯 Inline comments: best-effort line mapping with exact-match fast path
- 🧮 Metrics + labels: severity histogram, counts, and `gpt-review:*` labels
- 🧾 GitHub Job Summary: clean markdown table per run
- 🚦 Merge gate (optional): fail the job on `REQUEST_CHANGES`
- ⚙️ Zero infra: runs entirely in GitHub Actions (uses OpenAI API)

---

## Quick Start

1. **Secrets**
   - `OPENAI_API_KEY` → your OpenAI key (project/org scoped)
   - `GITHUB_TOKEN`   → provided automatically by Actions

2. **Workflow**

Create `.github/workflows/pr-review.yml`:

```yaml
name: PR Review (GPT)

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: read
  pull-requests: write
  issues: write   # for labeling

jobs:
  review:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version-file: ".python-version"

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Sync deps
        run: uv sync --locked --all-extras

      - name: Run PR review
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GITHUB_TOKEN: ${{ github.token }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          PULL_REQUEST_NUMBER: ${{ github.event.pull_request.number }}
          REVIEW_MODE: review            # "comment" for single comment
          ENABLE_AUTO_LABELS: "true"
          ENABLE_JOB_SUMMARY: "true"
          ENFORCE_GATE_ON_CI: "false"
        run: uv run python -m app.cli_review

      - name: 🧾 Job Summary
        if: always()
        run: uv run python -m tools.ci_summary

      - name: 🚦 Enforce Gate (optional)
        if: always()
        run: uv run python -m tools.ci_status
```

3. **Optional repo config**

Add `.gpt-pr-bot.yml` at repo root (overrides env & defaults):

```yaml
review_mode: comment          # or "review"
severity_gate: high           # off|low|medium|high
max_files: 6
max_patch_chars: 8000
max_total_patch_chars: 24000

only_changed_lines: true
changed_context_lines: 2
include_rules_preamble: true

enable_auto_labels: true
label_prefix: gpt-review

enable_job_summary: true
enforce_gate_on_ci: false

include_globs: []
exclude_globs:
  - "**/*.lock"
  - "**/*.png"
  - "**/*.jpg"
  - "**/dist/**"
  - "**/build/**"
```

Ignore patterns (one per line): `.gpt-pr-bot-ignore`

---

## Local Dev

```bash
# deps
uv sync

# tests / lint / fmt
uv run pytest -v
uv run ruff check .
uv run ruff format .

# run review locally (needs env vars, see below)
uv run python -m app.cli_review
```

Required env when running locally:

```bash
export OPENAI_API_KEY=sk-...
export GITHUB_TOKEN=ghp_...         # personal token if testing API calls
export GITHUB_REPOSITORY=owner/repo
export PULL_REQUEST_NUMBER=123
```

Job summary & status helpers:

```bash
uv run python -m tools.ci_summary
uv run python -m tools.ci_status
```

---

## How It Works (high level)

```
PR -> list files -> filter/exclude -> truncate -> (optional) slim changed lines
   -> batch by total chars -> build LLM prompt per batch -> parse structured JSON
   -> post inline PR review (or single comment) -> compute metrics & labels
   -> write .review_event & .review_report.json -> Job Summary -> optional gate
```

---

## Settings (selected)

| Key | Type | Default | Notes |
|---|---:|---:|---|
| `review_mode` | str | `comment` | `comment` or `review` (inline) |
| `severity_gate` | str | `high` | `off|low|medium|high` (escalates to request changes) |
| `max_files` | int | `6` | number of files analyzed |
| `max_patch_chars` | int | `8000` | per-file cap |
| `max_total_patch_chars` | int | `24000` | per batch |
| `only_changed_lines` | bool | `true` | slim hunks to +/- with context |
| `changed_context_lines` | int | `2` | context lines around changes |
| `enable_auto_labels` | bool | `true` | adds `gpt-review:*` labels |
| `enable_job_summary` | bool | `true` | writes Actions Job Summary |
| `enforce_gate_on_ci` | bool | `false` | fail job on `REQUEST_CHANGES` |
| `label_prefix` | str | `gpt-review` | label namespace |

All settings can come from:
- environment variables (e.g. `ENABLE_JOB_SUMMARY=true`)
- `.gpt-pr-bot.yml`
- `.env` (loaded by Pydantic)

---

## Security & Cost

- Never put secrets in comments or logs.
- Diff truncation + slimming significantly reduce tokens.
- You can cap `openai_max_tokens` and `temperature` in `app/settings.py`.

---

## License

MIT
