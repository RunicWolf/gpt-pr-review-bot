import asyncio
import os
from typing import List, Dict

from app.settings import settings
from app.services.github import GitHubClient
from app.services.github_reviews import GitHubReviewsClient
from app.services.llm import LLMClient
from app.review_strategy import build_llm_prompt_from_patches, parse_llm_json_or_fallback, RULES_PREAMBLE
from app.inline_mapper import guess_line_for_hint

def _truncate_patch(patch: str, max_chars: int) -> str:
    if patch and len(patch) > max_chars:
        tail = "\n\n...[truncated]..."
        return patch[: max_chars - len(tail)] + tail
    return patch or ""

def _markdown_header() -> str:
    hdr = "## 🤖 GPT Code Review (alpha)\n"
    if settings.include_rules_preamble:
        hdr += RULES_PREAMBLE + "\n"
    return hdr

async def main() -> int:
    repo = settings.github_repository or os.getenv("GITHUB_REPOSITORY")
    pr_number = settings.pull_request_number or os.getenv("PULL_REQUEST_NUMBER")
    token = settings.github_token or os.getenv("GITHUB_TOKEN")
    if pr_number is not None and isinstance(pr_number, str):
        pr_number = int(pr_number)

    if not repo or not pr_number or not token or not settings.openai_api_key:
        print("Missing required configuration. Need GITHUB_TOKEN, OPENAI_API_KEY, GITHUB_REPOSITORY, PULL_REQUEST_NUMBER.")
        return 2

    gh = GitHubClient(token=token)
    files = await gh.list_pr_files(repo, int(pr_number))

    patches: List[Dict] = []
    for f in files[: settings.max_files]:
        if "patch" in f and f["patch"]:
            patches.append({
                "filename": f["filename"],
                "patch": _truncate_patch(f["patch"], settings.max_patch_chars),
            })

    if not patches:
        body = "🤖 No text patches found to review (maybe only binary or too large files)."
        await gh.post_issue_comment(repo, int(pr_number), body)
        print(body)
        return 0

    # LLM
    llm = LLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    system, user = build_llm_prompt_from_patches(patches)
    raw = llm.review_patches_json(patches, system, user)["text"]
    parsed = parse_llm_json_or_fallback(raw)

    summary_md = parsed.get("summary_markdown", "").strip() or "_No summary_"
    header = _markdown_header()
    footer = "\n\n---\n_This is an automated first-pass review. Treat suggestions as guidance._"
    top_body = header + summary_md + footer

    # Inline mode?
    inline_mode = (settings.review_mode.lower() == "review")
    if not inline_mode:
        await gh.post_issue_comment(repo, int(pr_number), top_body)
        print("Posted single comment.")
        return 0

    # Attempt inline review
    # Build comment objects limited by MAX_INLINE_COMMENTS
    filename_to_patch = {p["filename"]: p["patch"] for p in patches}
    comments_payload: List[Dict] = []
    count = 0
    for f in parsed.get("files", []):
        fname = f.get("filename")
        if not fname or fname not in filename_to_patch:
            continue
        patch = filename_to_patch[fname]
        for c in f.get("comments", []):
            if count >= settings.max_inline_comments:
                break
            hint = c.get("line_hint", "") or ""
            line = guess_line_for_hint(patch, hint)
            if line is None:
                continue
            msg = c.get("message", "").strip()
            if not msg:
                continue
            comments_payload.append({
                "path": fname,
                "side": "RIGHT",
                "line": line,
                "body": msg,
            })
            count += 1

    if not comments_payload:
        # fallback to top-level comment if we couldn’t map lines
        await gh.post_issue_comment(repo, int(pr_number), top_body)
        print("No inline placements; posted single comment.")
        return 0

    # Try to create a PR review; if it fails (e.g., any invalid line),
    # fall back to the single comment so we still provide value.
    gh_reviews = GitHubReviewsClient(token=token)
    try:
        await gh_reviews.create_review(
            repo=repo,
            pull_number=int(pr_number),
            body=top_body,
            comments=comments_payload,
            event="COMMENT",
        )
        print(f"Posted PR review with {len(comments_payload)} inline comment(s).")
    except Exception as e:
        print(f"Inline review failed ({e}); falling back to single comment.")
        await gh.post_issue_comment(repo, int(pr_number), top_body)

    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
