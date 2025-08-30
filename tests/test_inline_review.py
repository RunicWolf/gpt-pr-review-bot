import asyncio
import app.cli_review as cli
from app.settings import settings
from app.services.github import GitHubClient
from app.services.github_reviews import GitHubReviewsClient
from app.services.llm import LLMClient


def test_inline_review_happy_path(monkeypatch):
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 11
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.review_mode = "review"
    settings.max_inline_comments = 5
    settings.max_patch_chars = 2000

    # one file with a clear added line that matches hint
    patch = "@@ -1,1 +1,2 @@\n context\n+added_line_security_check()\n"

    async def fake_list_pr_files(self, repo, pr):
        return [{"filename": "app/main.py", "patch": patch}]

    # LLM returns JSON as instructed
    def fake_complete_json(self, system, user):
        return (
            "{"
            ' "summary_markdown":"- Summary here",'
            ' "files":[{"filename":"app/main.py",'
            '           "comments":[{"line_hint":"security_check", "message":"Consider validating inputs."}]}]'
            "}"
        )

    posted_review = {"called": False, "count": 0, "body": ""}

    async def fake_create_review(
        self, repo, pull_number, body, comments, event="COMMENT"
    ):
        posted_review["called"] = True
        posted_review["count"] = len(comments)
        posted_review["body"] = body
        return {"id": 123}

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(LLMClient, "complete_json", fake_complete_json, raising=True)
    monkeypatch.setattr(
        GitHubReviewsClient, "create_review", fake_create_review, raising=True
    )

    rc = asyncio.run(cli.main())
    assert rc == 0
    assert posted_review["called"] is True
    assert posted_review["count"] == 1
    assert "Summary here" in posted_review["body"]


def test_inline_review_fallback_to_single_comment(monkeypatch):
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 12
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.review_mode = "review"

    # No added lines in patch -> mapping fails -> fallback to issue comment
    patch = "@@ -1,1 +1,1 @@\n context\n"  # no '+' lines

    async def fake_list_pr_files(self, repo, pr):
        return [{"filename": "app/main.py", "patch": patch}]

    def fake_complete_json(self, system, user):
        return (
            "{"
            ' "summary_markdown":"- No inline placements",'
            ' "files":[{"filename":"app/main.py",'
            '           "comments":[{"line_hint":"anything", "message":"Try X."}]}]'
            "}"
        )

    posted_issue_comment = {"called": False, "body": ""}

    async def fake_post_issue_comment(self, repo, issue_number, body):
        posted_issue_comment["called"] = True
        posted_issue_comment["body"] = body
        return {"id": 456}

    async def fake_create_review(self, *args, **kwargs):
        raise RuntimeError("Should not be called in this test")

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(LLMClient, "complete_json", fake_complete_json, raising=True)
    monkeypatch.setattr(
        GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True
    )
    monkeypatch.setattr(
        GitHubReviewsClient, "create_review", fake_create_review, raising=True
    )

    rc = asyncio.run(cli.main())
    assert rc == 0
    assert posted_issue_comment["called"] is True
    assert "No inline placements" in posted_issue_comment["body"]
