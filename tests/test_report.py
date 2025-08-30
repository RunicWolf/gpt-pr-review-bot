import asyncio
import json
from pathlib import Path

import app.cli_review as cli
from app.settings import settings
from app.services.github import GitHubClient
from app.services.llm import LLMClient


def test_report_file_created(monkeypatch, tmp_path: Path):
    # Run inside a temp dir so report files don't leak into repo
    monkeypatch.chdir(tmp_path)

    settings.github_repository = "owner/repo"
    settings.pull_request_number = 999
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.review_mode = "comment"
    settings.include_globs = []
    settings.exclude_globs = []
    settings.max_files = 5
    settings.max_total_patch_chars = 5000
    settings.max_patch_chars = 2000

    async def fake_list_pr_files(self, repo, pr):
        return [{"filename": "app/main.py", "patch": "@@ -1 +1 @@\n+print('ok')\n"}]

    posted = {"calls": 0}

    async def fake_post_issue_comment(self, repo, issue_number, body):
        posted["calls"] += 1
        return {"id": 1}

    def fake_review_patches_json(self, patches, system, user):
        return {"text": '{"summary_markdown":"OK","decision":"comment","files":[]}'}

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(
        GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True
    )
    monkeypatch.setattr(
        LLMClient, "review_patches_json", fake_review_patches_json, raising=True
    )

    rc = asyncio.run(cli.main())
    assert rc == 0
    assert posted["calls"] == 1

    # Check files
    report = tmp_path / ".review_report.json"
    evt = tmp_path / ".review_event"
    assert report.exists()
    assert evt.exists()
    data = json.loads(report.read_text("utf-8"))
    assert data["overall_event"] in ("COMMENT", "REQUEST_CHANGES")
    assert data["batches"] and isinstance(data["batches"], list)
