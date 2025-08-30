# tools/ci_summary.py
import json
import os
from pathlib import Path

from app.settings import settings

REPORT = Path(".review_report.json")


def _read_json_any_encoding(path: Path):
    # Try common Windows/PowerShell encodings first
    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-8", "latin-1"):
        try:
            return json.loads(path.read_text(encoding=enc))
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError:
            # If decoding worked but JSON is invalid, don't try other encodings
            raise
    # Last resort: binary -> strip BOM if any, then utf-8
    raw = path.read_bytes()
    for bom in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):
        if raw.startswith(bom):
            raw = raw[len(bom) :]
            break
    return json.loads(raw.decode("utf-8", errors="replace"))


def main() -> int:
    if not settings.enable_job_summary:
        print("Job summary disabled via settings.enable_job_summary.")
        return 0

    if not REPORT.exists():
        print("No .review_report.json found; nothing to summarize.")
        return 0

    try:
        data = _read_json_any_encoding(REPORT)
    except Exception as e:
        print(f"Could not read/parse .review_report.json: {e}")
        return 0

    overall = data.get("overall_event", "COMMENT")
    metrics = data.get("metrics", {})
    hist = metrics.get("overall_severity_histogram", {})
    files_reviewed = metrics.get("overall_files_reviewed", 0)
    comments = metrics.get("overall_comments", 0)

    title = settings.summary_title or "GPT Code Review"

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    status_emoji = "✅" if overall == "COMMENT" else "❌"
    lines.append(f"**Outcome:** {status_emoji} `{overall}`")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Files | Comments | High | Medium | Low |")
    lines.append("|------:|---------:|-----:|-------:|----:|")
    lines.append(
        f"| {files_reviewed} | {comments} | {hist.get('high',0)} | {hist.get('medium',0)} | {hist.get('low',0)} |"
    )
    lines.append("")
    lines.append("## Batches")
    lines.append("")
    for b in data.get("batches", []):
        lines.append(f"### Batch {b.get('batch')}/{b.get('total_batches')}")
        lines.append(f"- **Event:** `{b.get('event')}`")
        files_list = ", ".join(b.get("files_in_batch", [])) or "—"
        lines.append(f"- **Files:** `{files_list}`")
        m = b.get("metrics", {})
        sh = m.get("severity_histogram", {})
        lines.append(
            f"- **Severities:** high={sh.get('high',0)}, medium={sh.get('medium',0)}, low={sh.get('low',0)}"
        )
        excerpt = (b.get("summary_excerpt") or "").strip()
        if excerpt:
            lines.append("")
            lines.append("> " + excerpt.replace("\n", "\n> "))
            lines.append("")
    lines.append("")
    lines.append(
        "_Tip: tune gates/filters in `.gpt-pr-bot.yml` or `.gpt-pr-bot-ignore`._"
    )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    md = "\n".join(lines)
    if summary_path:
        Path(summary_path).write_text(md, encoding="utf-8")
    else:
        # Fallback to stdout if not running in Actions
        print(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
