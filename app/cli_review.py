import asyncio
import json
import os
from typing import List, Dict

from app.settings import settings
from app.services.github import GitHubClient
from app.services.github_reviews import GitHubReviewsClient
from app.services.llm import LLMClient
from app.review_strategy import (
    build_llm_prompt_from_patches,
    parse_llm_json_or_fallback,
    RULES_PREAMBLE,
)
from app.inline_mapper import guess_line_for_hint
from app.file_filters import should_include
from app.diff_slimmer import slim_patch_to_changed  # <-- slimming helper

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}
STATUS_FILE = ".review_event"
REPORT_FILE = ".review_report.json"


def _write_event(event: str):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(event)
    except Exception:
        pass


def _write_report(report: dict):
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass


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


def chunk_patches(patches: List[Dict], max_chars: int) -> List[List[Dict]]:
    """Greedy chunking of patches so each batch stays under max_chars."""
    batches: List[List[Dict]] = []
    cur: List[Dict] = []
    cur_len = 0
    for p in patches:
        plen = len(p["patch"])
        if cur and cur_len + plen > max_chars:
            batches.append(cur)
            cur = []
            cur_len = 0
        cur.append(p)
        cur_len += plen
    if cur:
        batches.append(cur)
    return batches


def _has_changes(p: str) -> bool:
    """Return True if unified diff has at least one real added/removed line."""
    for ln in p.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            return True
        if ln.startswith("-") and not ln.startswith("---"):
            return True
    return False


def _merge_hist(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + int(v)
    return out


def _metrics_from_parsed(parsed: Dict) -> Dict:
    """
    Build severity histogram and counts from the parsed LLM JSON:
    {
      files: [
        { filename, comments: [{severity: low|medium|high, ...}, ...] },
        ...
      ]
    }
    """
    severity = {"low": 0, "medium": 0, "high": 0}
    files_count = 0
    comments_count = 0

    for f in parsed.get("files", []):
        files_count += 1
        for c in f.get("comments", []):
            sev = str(c.get("severity", "medium")).lower()
            if sev not in severity:
                sev = "medium"
            severity[sev] += 1
            comments_count += 1

    return {
        "severity_histogram": severity,
        "files_count": files_count,
        "comments_count": comments_count,
    }


async def _post_single_comment(
    gh: GitHubClient, repo: str, pr_number: int, body: str, event: str
):
    # event is "COMMENT" or "REQUEST_CHANGES" — we still post a single issue comment for visibility
    _write_event(event)
    await gh.post_issue_comment(repo, pr_number, body)


async def _post_inline_review(
    gh_reviews: GitHubReviewsClient,
    gh: GitHubClient,
    repo: str,
    pr_number: int,
    body: str,
    comments_payload: List[Dict],
    event: str,
):
    try:
        await gh_reviews.create_review(
            repo=repo,
            pull_number=pr_number,
            body=body,
            comments=comments_payload,
            event=event,
        )
        _write_event(event)
        print(
            f"Posted PR review with {len(comments_payload)} inline comment(s), event={event}."
        )
    except Exception as e:
        print(f"Inline review failed ({e}); falling back to single comment.")
        await _post_single_comment(gh, repo, pr_number, body, event)


async def main() -> int:
    repo = settings.github_repository or os.getenv("GITHUB_REPOSITORY")
    pr_number = settings.pull_request_number or os.getenv("PULL_REQUEST_NUMBER")
    token = settings.github_token or os.getenv("GITHUB_TOKEN")
    if pr_number is not None and isinstance(pr_number, str):
        pr_number = int(pr_number)

    if not repo or not pr_number or not token or not settings.openai_api_key:
        print(
            "Missing required configuration. Need GITHUB_TOKEN, OPENAI_API_KEY, GITHUB_REPOSITORY, PULL_REQUEST_NUMBER."
        )
        return 2

    gh = GitHubClient(token=token)
    files = await gh.list_pr_files(repo, int(pr_number))

    # Filter + per-file truncation + total limit (pre-batching)
    selected: List[Dict] = []
    total_chars = 0
    for f in files:
        fname = f.get("filename")
        if not fname:
            continue
        if not should_include(fname, settings.include_globs, settings.exclude_globs):
            continue
        if "patch" not in f or not f["patch"]:
            continue

        # Truncate large file diff
        patch = _truncate_patch(f["patch"], settings.max_patch_chars)

        # Slim to only changed lines with N lines of context; drop hunks with ignore marker.
        # IMPORTANT: only slim when there are real +/- changes; otherwise keep patch as-is
        slimmed = patch
        if settings.only_changed_lines and _has_changes(patch):
            slimmed = slim_patch_to_changed(
                patch=patch,
                ctx=settings.changed_context_lines,
                marker=(settings.ignore_inline_marker or None),
            )
            # Keep output stable for tests that check string suffix exactly
            slimmed = slimmed.rstrip("\n")

        # If slimming removed everything (e.g., all hunks had ignore marker), skip file
        if not slimmed.strip():
            continue

        # Respect total cap using the slimmed size
        if total_chars + len(slimmed) > settings.max_total_patch_chars and selected:
            # stop taking more files once we hit the total cap
            break

        selected.append({"filename": fname, "patch": slimmed})
        total_chars += len(slimmed)
        if len(selected) >= settings.max_files:
            break

    if not selected:
        body = "🤖 No text patches found to review after filtering (maybe only binary/large/excluded files)."
        await gh.post_issue_comment(repo, int(pr_number), body)
        _write_event("COMMENT")
        # write a minimal report so CI summary has something to show
        _write_report(
            {
                "overall_event": "COMMENT",
                "batches": [],
                "reason": "no_patches_after_filtering",
                "review_mode": settings.review_mode,
                "severity_gate": settings.severity_gate,
                "max_files": settings.max_files,
                "max_inline_comments": settings.max_inline_comments,
            }
        )
        print(body)
        return 0

    # Batch the selected patches
    batches = chunk_patches(selected, settings.max_total_patch_chars)
    total_batches = len(batches)

    llm = LLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    inline_mode = settings.review_mode.lower() == "review"
    header_base = _markdown_header()
    footer = "\n\n---\n_This is an automated first-pass review. Treat suggestions as guidance._"

    gh_reviews = GitHubReviewsClient(token=token)

    # For the final rollup report
    all_batches_meta: List[Dict] = []
    overall_sev = {"low": 0, "medium": 0, "high": 0}
    overall_files = 0
    overall_comments = 0

    # Process each batch independently
    for idx, batch in enumerate(batches, start=1):
        system, user = build_llm_prompt_from_patches(batch)
        raw = llm.review_patches_json(batch, system, user)["text"]
        parsed = parse_llm_json_or_fallback(raw)

        # Per-batch metrics
        m = _metrics_from_parsed(parsed)
        overall_sev = _merge_hist(overall_sev, m["severity_histogram"])
        overall_files += m["files_count"]
        overall_comments += m["comments_count"]

        # Decide event (respect local gate)
        llm_decision = str(parsed.get("decision", "comment")).lower()
        local_decision = _decision_from_severities(parsed.get("files", []))
        final_decision = llm_decision
        if (
            settings.severity_gate.lower() != "off"
            and local_decision == "request_changes"
        ):
            final_decision = "request_changes"
        event = (
            "COMMENT" if final_decision in ("approve", "comment") else "REQUEST_CHANGES"
        )

        # Build body with batch tag
        summary_md = parsed.get("summary_markdown", "").strip() or "_No summary_"
        header = header_base.replace(
            "## 🤖 GPT Code Review",
            f"## 🤖 GPT Code Review (batch {idx}/{total_batches})",
        )
        body = header + summary_md + footer

        # Inline placement for this batch
        filename_to_patch = {p["filename"]: p["patch"] for p in batch}
        comments_payload: List[Dict] = []
        count = 0
        if inline_mode:
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
                    comments_payload.append(
                        {
                            "path": fname,
                            "side": "RIGHT",
                            "line": line,
                            "body": msg,
                        }
                    )
                    count += 1

        # Post review/comment for this batch
        if inline_mode and comments_payload:
            await _post_inline_review(
                gh_reviews, gh, repo, int(pr_number), body, comments_payload, event
            )
        else:
            # Fall back to single comment if not inline mode or no mappable inline comments
            await _post_single_comment(gh, repo, int(pr_number), body, event)
            print(
                f"[batch {idx}/{total_batches}] "
                f"{'No inline placements; ' if inline_mode and not comments_payload else ''}"
                f"posted single comment (decision: {final_decision})."
            )

        # Collect minimal per-batch metadata for reporting
        all_batches_meta.append(
            {
                "batch": idx,
                "total_batches": total_batches,
                "final_decision": final_decision,
                "event": event,
                "summary_excerpt": summary_md[:180],
                "files_in_batch": [p["filename"] for p in batch],
                "inline_comments_posted": len(comments_payload) if inline_mode else 0,
                "metrics": m,  # <-- per-batch metrics
            }
        )

    # Roll up an overall event across batches (REQUEST_CHANGES wins if any batch requested it)
    overall_event = "COMMENT"
    for m in all_batches_meta:
        if m.get("event") == "REQUEST_CHANGES":
            overall_event = "REQUEST_CHANGES"
            break

    _write_event(overall_event)
    _write_report(
        {
            "overall_event": overall_event,
            "review_mode": settings.review_mode,
            "severity_gate": settings.severity_gate,
            "max_files": settings.max_files,
            "max_inline_comments": settings.max_inline_comments,
            "metrics": {
                "overall_severity_histogram": overall_sev,
                "overall_files_reviewed": overall_files,
                "overall_comments": overall_comments,
            },
            "batches": all_batches_meta,
        }
    )

    # Optional: apply PR labels summarizing the review outcome + highest severity
    try:
        if settings.enable_auto_labels:
            prefix = (settings.label_prefix or "gpt-review").strip() or "gpt-review"
            outcome_label = f"{prefix}:{'request-changes' if overall_event == 'REQUEST_CHANGES' else 'comment'}"

            if overall_sev.get("high", 0) > 0:
                sev_label = f"{prefix}:high"
            elif overall_sev.get("medium", 0) > 0:
                sev_label = f"{prefix}:medium"
            else:
                sev_label = f"{prefix}:low"

            await gh.add_labels(repo, int(pr_number), [outcome_label, sev_label])
    except Exception as e:
        # Non-fatal: labeling is best-effort
        print(f"Labeling skipped: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
