import asyncio
import json
from pathlib import Path

import app.cli_review as cli
from app.settings import settings
from app.services.github import GitHubClient
from app.services.llm import LLMClient


def test_metrics_and_labels(monkeypatch, tmp_path: Path):
    # Work in temp dir
    monkeypatch.chdir(tmp_path)

    # Settings
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 55
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.review_mode = "comment"
    settings.include_globs = []
    settings.exclude_globs = []
    settings.enable_auto_labels = True
    settings.label_prefix = "gpt-review"
    settings.severity_gate = "off"  # <-- add this line

    # PR files (one file, two comments with different severities)
    async def fake_list_pr_files(self, repo, pr):
        return [{"filename": "app/x.py", "patch": "@@ -1 +1 @@\n+print('x')\n"}]

    # Capture labels and posted comments
    posted = {"calls": 0}
    labels_called = {"labels": None}

    async def fake_post_issue_comment(self, repo, issue, body):
        posted["calls"] += 1
        return {"id": 1}

    async def fake_add_labels(self, repo, issue_number, labels):
        labels_called["labels"] = labels
        return {"ok": True}

    # LLM returns two comments in different severities
    def fake_review_patches_json(self, patches, system, user):
        return {
            "text": json.dumps(
                {
                    "summary_markdown": "Summary",
                    "decision": "comment",
                    "files": [
                        {
                            "filename": "app/x.py",
                            "comments": [
                                {
                                    "line_hint": "print",
                                    "message": "nit",
                                    "severity": "low",
                                },
                                {
                                    "line_hint": "print",
                                    "message": "check",
                                    "severity": "high",
                                },
                            ],
                        }
                    ],
                }
            )
        }

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(
        GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True
    )
    monkeypatch.setattr(GitHubClient, "add_labels", fake_add_labels, raising=True)
    monkeypatch.setattr(
        LLMClient, "review_patches_json", fake_review_patches_json, raising=True
    )

    rc = asyncio.run(cli.main())
    assert rc == 0
    assert posted["calls"] == 1

    # Report exists with metrics
    report = tmp_path / ".review_report.json"
    data = json.loads(report.read_text("utf-8"))
    hist = data["metrics"]["overall_severity_histogram"]
    assert hist["low"] == 1 and hist["high"] == 1

    # Labels contain severity & outcome
    assert labels_called["labels"] is not None
    assert "gpt-review:comment" in labels_called["labels"]
    assert "gpt-review:high" in labels_called["labels"]
