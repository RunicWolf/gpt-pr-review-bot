import asyncio
import types
from typing import List, Dict

import builtins
import app.cli_review as cli  # imports settings + classes
from app.services.github import GitHubClient
from app.services.llm import LLMClient
from app.settings import settings


def _run(coro):
    """Run an async coroutine to completion (no pytest-asyncio needed)."""
    return asyncio.run(coro)


def test_cli_review_posts_review_when_patches_present(monkeypatch):

    

    # --- arrange ---
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 42
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.openai_model = "gpt-4o-mini"
    settings.max_files = 5
    settings.max_patch_chars = 2000
    settings.review_mode = "comment"  # ensure single comment path

    # Neutralize repo config filtering for this test
    settings.include_globs = []
    settings.exclude_globs = []

    posted_bodies: List[str] = []

    async def fake_list_pr_files(self, repo: str, pr_number: int) -> List[Dict]:
        assert repo == "owner/repo"
        assert pr_number == 42
        return [
            {"filename": "app/main.py", "patch": "@@ -1,4 +1,6 @@\n- old\n+ new\n"},
            {"filename": "README.md", "patch": "@@ -1 +1 @@\n- hello\n+ world\n"},
        ]

    async def fake_post_issue_comment(self, repo: str, issue_number: int, body: str) -> Dict:
        posted_bodies.append(body)
        return {"id": 123, "body": body}

    def fake_review_patches_json(self, patches: List[Dict], system: str, user: str) -> Dict:
        # Ensure we received structured patches
        assert isinstance(patches, list) and patches
        assert patches[0]["filename"] == "app/main.py"
        # Return JSON the CLI will parse
        return {"text": '{"summary_markdown":"- Looks good overall.\\n- Consider adding more tests.","files":[]}'}

    # Monkeypatch network/API layers
    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True)
    monkeypatch.setattr(LLMClient, "review_patches_json", fake_review_patches_json, raising=True)

    # --- act ---
    rc = asyncio.run(cli.main())

    # --- assert ---
    assert rc == 0
    assert len(posted_bodies) == 1
    body = posted_bodies[0]
    assert body.startswith("## 🤖 GPT Code Review")
    assert "Looks good overall" in body
    assert "_This is an automated first-pass review." in body



def test_cli_review_handles_no_patches(monkeypatch):
    # --- arrange ---
    settings.github_repository = "owner/repo"
    settings.pull_request_number = 7
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"

    posted_bodies: List[str] = []

    async def fake_list_pr_files(self, repo: str, pr_number: int) -> List[Dict]:
        # No 'patch' keys, e.g., binary files or empty diff
        return [{"filename": "diagram.png"}, {"filename": "large.bin"}]

    async def fake_post_issue_comment(self, repo: str, issue_number: int, body: str) -> Dict:
        posted_bodies.append(body)
        return {"id": 456, "body": body}

    # Monkeypatch GitHub; LLM won’t be called
    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True)

    # --- act ---
    rc = _run(cli.main())

    # --- assert ---
    assert rc == 0
    assert len(posted_bodies) == 1
    assert "No text patches found to review" in posted_bodies[0]

def test_cli_review_truncates_large_patches(monkeypatch):
    from app.settings import settings
    from app.services.github import GitHubClient
    from app.services.llm import LLMClient
    import app.cli_review as cli

    

    settings.github_repository = "owner/repo"
    settings.pull_request_number = 101
    settings.github_token = "ghs_mock"
    settings.openai_api_key = "sk-mock"
    settings.openai_model = "gpt-4o-mini"
    settings.review_mode = "comment"

    # Neutralize repo config filtering for this test
    settings.include_globs = []
    settings.exclude_globs = []

    # Make truncation very strict so it's easy to assert
    settings.max_patch_chars = 50
    settings.max_files = 3

    long_patch = "@@ -1,2 +1,2 @@\n" + ("+" * 500)  # very long diff

    async def fake_list_pr_files(self, repo: str, pr_number: int):
        return [{"filename": "app/very_long.py", "patch": long_patch}]

    posted_bodies = []
    async def fake_post_issue_comment(self, repo: str, issue_number: int, body: str):
        posted_bodies.append(body)
        return {"id": 999, "body": body}

    def fake_review_patches_json(self, patches, system, user):
        # Assert truncation happened BEFORE LLM call
        assert len(patches) == 1
        p = patches[0]
        assert p["filename"] == "app/very_long.py"
        assert p["patch"].endswith("...[truncated]...")
        assert len(p["patch"]) <= settings.max_patch_chars
        # Return JSON summary for the top-level comment path
        return {"text": '{"summary_markdown":"Truncation verified.","files":[]}'}

    monkeypatch.setattr(GitHubClient, "list_pr_files", fake_list_pr_files, raising=True)
    monkeypatch.setattr(GitHubClient, "post_issue_comment", fake_post_issue_comment, raising=True)
    monkeypatch.setattr(LLMClient, "review_patches_json", fake_review_patches_json, raising=True)

    # --- act ---
    rc = asyncio.run(cli.main())

    # --- assert ---
    assert rc == 0
    assert posted_bodies and "Truncation verified." in posted_bodies[0]

