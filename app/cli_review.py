import asyncio
import os
from typing import List, Dict

from app.settings import settings
from app.services.github import GitHubClient
from app.services.llm import LLMClient

def _truncate_patch(patch: str, max_chars: int) -> str:
    if patch and len(patch) > max_chars:
        tail = "\n\n...[truncated]..."
        return patch[: max_chars - len(tail)] + tail
    return patch or ""

async def main() -> int:
    repo = settings.github_repository or os.getenv("GITHUB_REPOSITORY")
    pr_number = settings.pull_request_number or os.getenv("PULL_REQUEST_NUMBER")
    token = settings.github_token or os.getenv("GITHUB_TOKEN")
    if pr_number is not None and isinstance(pr_number, str):
        # from env it's a string
        pr_number = int(pr_number)

    if not repo or not pr_number or not token or not settings.openai_api_key:
        print("Missing required configuration. Need GITHUB_TOKEN, OPENAI_API_KEY, GITHUB_REPOSITORY, PULL_REQUEST_NUMBER.")
        return 2

    gh = GitHubClient(token=token)
    files = await gh.list_pr_files(repo, int(pr_number))

    # Collect patches (only files that include 'patch'—binary files won’t)
    patches: List[Dict] = []
    for f in files[: settings.max_files]:
        if "patch" in f and f["patch"]:
            patches.append({
                "filename": f["filename"],
                "patch": _truncate_patch(f["patch"], settings.max_patch_chars),
            })

    if not patches:
        # still post a friendly note
        body = "🤖 No text patches found to review (maybe only binary or too large files)."
        await gh.post_issue_comment(repo, int(pr_number), body)
        print(body)
        return 0

    llm = LLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    review_md = llm.review_patches(patches)

    header = "## 🤖 GPT Code Review (alpha)\n"
    footer = (
        "\n\n---\n_This is an automated first-pass review. "
        "Please treat suggestions as guidance; maintainers make final decisions._"
    )
    body = header + review_md + footer

    await gh.post_issue_comment(repo, int(pr_number), body)
    print("Posted review comment to PR #", pr_number)
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
