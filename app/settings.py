from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
