from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config_loader import load_repo_config, load_ignore_file


class Settings(BaseSettings):
    # --- OpenAI ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # You can switch to "gpt-4o"
    openai_temperature: float = 0.2
    openai_max_tokens: int = 800  # Safety cap

    # --- GitHub ---
    github_token: str = ""  # In Actions, GitHub passes this as GITHUB_TOKEN
    github_repository: Optional[str] = None  # e.g., "RunicWolf/gpt-pr-review-bot"
    pull_request_number: Optional[int] = None

    # --- Safety / cost controls ---
    max_files: int = 6
    max_patch_chars: int = 8000  # Per-file cap
    max_total_patch_chars: int = 24000  # Total across selected files

    # --- Review behavior ---
    review_mode: str = "comment"  # "comment" (single) or "review" (inline PR review)
    max_inline_comments: int = 12  # Max inline comments we’ll attempt
    include_rules_preamble: bool = True  # Adds rules summary to markdown header
    severity_gate: str = "high"  # "off" | "low" | "medium" | "high"

    # --- File filtering ---
    include_globs: List[str] = []  # e.g., ["app/**", "src/**"]
    exclude_globs: List[str] = [
        "**/*.lock",
        "**/package-lock.json",
        "**/yarn.lock",
        "**/pnpm-lock.yaml",
        "**/poetry.lock",
        "**/*.min.js",
        "**/*.map",
        "**/dist/**",
        "**/build/**",
        "**/node_modules/**",
        "**/*.png",
        "**/*.jpg",
        "**/*.jpeg",
        "**/*.gif",
        "**/*.pdf",
        "**/*.zip",
        "**/*.tar.gz",
        "**/*.jar",
        "**/*.bin",
    ]

    # --- Noise controls (Step 7) ---
    # Only send changed lines (+/-) to the model, not the full patch context
    only_changed_lines: bool = True
    # Number of surrounding context lines to keep around each change hunk
    changed_context_lines: int = 2

    # Extra ignore sources
    # Repo-root file with glob patterns to skip (similar to .gitignore)
    ignore_file: str = ".gpt-pr-bot-ignore"
    # Inline marker to skip a hunk, e.g., "# gpt-bot-ignore"
    ignore_inline_marker: str = "gpt-bot-ignore"

    # --- Metrics & Labels (Step 8) ---
    enable_auto_labels: bool = True
    label_prefix: str = (
        "gpt-review"  # labels like gpt-review:request-changes, gpt-review:high
    )

    # --- Pydantic settings ---
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- CI summary & gate enforcement ---
    enable_job_summary: bool = True  # write a Markdown job summary to GitHub Actions
    enforce_gate_on_ci: bool = False  # if True and REQUEST_CHANGES, fail the job
    summary_title: str = "🤖 GPT Code Review"


# Initialize with env first
settings = Settings()

# Overlay with repo config if present
repo_conf = load_repo_config()
for k, v in repo_conf.items():
    key = k.lower()
    if hasattr(settings, key):
        setattr(settings, key, v)

# Merge ignore file patterns into exclude_globs (if configured and present)
try:
    ignore_path = settings.ignore_file
    if ignore_path:
        extra = load_ignore_file(ignore_path)
        if extra:
            # Keep order, remove duplicates
            settings.exclude_globs = list(
                dict.fromkeys([*settings.exclude_globs, *extra])
            )
except Exception:
    # Non-fatal if ignore file can't be read
    pass
