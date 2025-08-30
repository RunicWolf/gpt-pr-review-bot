from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from app.config_loader import load_repo_config

class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # works well; you can switch to "gpt-4o"

    # GitHub
    github_token: str = ""  # in Actions, GitHub passes this as GITHUB_TOKEN
    github_repository: Optional[str] = None  # e.g., "RunicWolf/gpt-pr-review-bot"
    pull_request_number: Optional[int] = None

    # Safety / cost controls
    max_files: int = 6
    max_patch_chars: int = 8000  # limit context size to control token usage

    review_mode: str = "comment"  # "comment" (single top-level) or "review" (inline PR review)
    max_inline_comments: int = 12  # cap the number of inline comments we’ll try to post
    include_rules_preamble: bool = True  # adds the rules summary in markdown header

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
    max_files: int = 6              # already present; keep here for clarity
    max_patch_chars: int = 8000     # per-file cap (already present)
    max_total_patch_chars: int = 24000  # total across files

    # --- Review severity / gating ---
    review_mode: str = "comment"   # "comment" or "review"
    max_inline_comments: int = 12
    severity_gate: str = "high"    # "off" | "low" | "medium" | "high"
    include_rules_preamble: bool = True

    # --- OpenAI runtime controls ---
    openai_temperature: float = 0.2
    openai_max_tokens: int = 800   # safety cap

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

# Overlay with repo config if present
repo_conf = load_repo_config()
for k, v in repo_conf.items():
    key = k.lower()
    if hasattr(settings, key):
        setattr(settings, key, v)