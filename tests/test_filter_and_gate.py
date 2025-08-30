import asyncio
from typing import List, Dict
import app.cli_review as cli
from app.settings import settings
from app.services.github import GitHubClient
from app.services.llm import LLMClient

def test_filters_skip_lock_and_binary(monkeypatch):
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 77
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.review_mode = "comment"
    settings.exclude_globs = ["**/*.lock", "**/*.png"]
    settings.include_globs = []  # include everything else
    settings.max_files = 10
    settings.max_total_patch_chars = 10000
    settings.max_patch_chars = 2000

    files_called = {"count": 0}
    async def fake_list_pr_files(self, repo, pr):
        files_called["count"] += 1
        return [
            {"filename": "yarn.lock", "patch": "@@ -1 +1 @@"},            # should be excluded
            {"filename": "diagram.png", "patch": "@@ -1 +1 @@"},          # should be excluded
            {"filename": "app/ok.py", "patch": "@@ -1,1 +1,1 @@\n+print('ok')\n"},  # include
        ]

    posted_bodies = []
    async def fake_post_issue_comment(self, repo, issue_number, body):
        posted_bodies.append(body)
        return {"id": 1}

    captured = {"got_patches": []}
    def fake_review_patches_json(self, patches, system, user):
        captured["got_patches"] = [p["filename"] for p in patches]
        return {"text": '{"summary_markdown":"Filtered ok","decision":"comment","files":[]}'}

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True)
    monkeypatch.setattr(LLMClient, "review_patches_json", fake_review_patches_json, raising=True)

    rc = asyncio.run(cli.main())
    assert rc == 0
    # Only "app/ok.py" should pass to the model
    assert captured["got_patches"] == ["app/ok.py"]
    # And a single comment should be posted
    assert posted_bodies and "Filtered ok" in posted_bodies[0]

def test_severity_gate_triggers_request_changes(monkeypatch):
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 88
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.review_mode = "review"
    settings.severity_gate = "high"  # gate on high
    settings.max_inline_comments = 5

    patch = "@@ -1,1 +1,2 @@\n context\n+dangerous_eval(user_input)\n"

    async def fake_list_pr_files(self, repo, pr):
        return [{"filename": "app/main.py", "patch": patch}]

    # Model returns decision=comment but includes a high severity comment -> gate should escalate to REQUEST_CHANGES
    def fake_complete_json(self, system, user):
        return (
            '{'
            ' "summary_markdown":"- Found a dangerous pattern",'
            ' "decision":"comment",'
            ' "files":[{"filename":"app/main.py",'
            '           "comments":[{"line_hint":"dangerous_eval", "message":"Avoid eval on user input", "severity":"high"}]}]'
            '}'
        )

    posted = {"event": None, "count": 0}
    async def fake_create_review(self, repo, pull_number, body, comments, event="COMMENT"):
        posted["event"] = event
        posted["count"] = len(comments)
        return {"id": 321}

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(LLMClient, "complete_json", fake_complete_json, raising=True)
    monkeypatch.setattr("app.services.github_reviews.GitHubReviewsClient.create_review", fake_create_review, raising=False)

    rc = asyncio.run(cli.main())
    assert rc == 0
    assert posted["event"] == "REQUEST_CHANGES"
    assert posted["count"] == 1
