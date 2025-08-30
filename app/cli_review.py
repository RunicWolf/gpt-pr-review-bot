import asyncio
import os
from typing import List, Dict

from app.settings import settings
from app.services.github import GitHubClient
from app.services.github_reviews import GitHubReviewsClient
from app.services.llm import LLMClient
from app.review_strategy import build_llm_prompt_from_patches, parse_llm_json_or_fallback, RULES_PREAMBLE
from app.inline_mapper import guess_line_for_hint
from app.file_filters import should_include

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

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

def _decision_from_severities(files: List[Dict]) -> str:
    """Compute a decision based on the configured gate and comment severities."""
    gate = (settings.severity_gate or "off").lower()
    if gate == "off":
        return "comment"
    threshold = SEVERITY_ORDER.get(gate, 3)  # default "high"
    most_severe = 0
    for f in files:
        for c in f.get("comments", []):
            sev = SEVERITY_ORDER.get(str(c.get("severity", "medium")).lower(), 2)
            most_severe = max(most_severe, sev)
    return "request_changes" if most_severe >= threshold else "comment"

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

    # Filter + size limits
    patches: List[Dict] = []
    total_chars = 0
    for f in files:
        fname = f.get("filename")
        if not fname:
            continue
        if not should_include(fname, settings.include_globs, settings.exclude_globs):
            continue
        if "patch" not in f or not f["patch"]:
            continue
        patch = _truncate_patch(f["patch"], settings.max_patch_chars)
        if total_chars + len(patch) > settings.max_total_patch_chars:
            # stop adding more files once we hit the total cap
            break
        patches.append({"filename": fname, "patch": patch})
        total_chars += len(patch)
        if len(patches) >= settings.max_files:
            break

    if not patches:
        body = "🤖 No text patches found to review after filtering (maybe only binary/large/excluded files)."
        await gh.post_issue_comment(repo, int(pr_number), body)
        print(body)
        return 0

    # LLM
    llm = LLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    system, user = build_llm_prompt_from_patches(patches)
    raw = llm.review_patches_json(patches, system, user)["text"]
    parsed = parse_llm_json_or_fallback(raw)

    # Decide whether to request changes (either model’s decision or local gate)
    llm_decision = str(parsed.get("decision", "comment")).lower()
    local_decision = _decision_from_severities(parsed.get("files", []))
    final_decision = llm_decision
    if settings.severity_gate.lower() != "off":
        # escalate to request_changes if local gate says so
        if local_decision == "request_changes":
            final_decision = "request_changes"

    summary_md = parsed.get("summary_markdown", "").strip() or "_No summary_"
    header = _markdown_header()
    footer = "\n\n---\n_This is an automated first-pass review. Treat suggestions as guidance._"
    top_body = header + summary_md + footer

    inline_mode = (settings.review_mode.lower() == "review")
    event = "COMMENT" if final_decision in ("approve", "comment") else "REQUEST_CHANGES"

    if not inline_mode:
        await gh.post_issue_comment(repo, int(pr_number), top_body)
        print(f"Posted single comment (decision: {final_decision}).")
        return 0

    # Inline review mode
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

    gh_reviews = GitHubReviewsClient(token=token)
    if comments_payload:
        try:
            await gh_reviews.create_review(
                repo=repo,
                pull_number=int(pr_number),
                body=top_body,
                comments=comments_payload,
                event=event,
            )
            print(f"Posted PR review with {len(comments_payload)} inline comment(s), event={event}.")
            return 0
        except Exception as e:
            print(f"Inline review failed ({e}); falling back to single comment.")

    await gh.post_issue_comment(repo, int(pr_number), top_body)
    print(f"No inline placements or error; posted single comment (decision: {final_decision}).")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
