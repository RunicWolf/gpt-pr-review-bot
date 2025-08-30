from typing import Dict, List, Optional
import httpx

class GitHubReviewsClient:
    """
    Minimal wrapper for creating a single PR review with multiple inline comments.
    Falls back to a top-level issue comment if needed in the CLI.
    """
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_review(
        self,
        repo: str,
        pull_number: int,
        body: str,
        comments: List[Dict],
        event: str = "COMMENT",  # COMMENT, REQUEST_CHANGES, APPROVE
    ) -> Dict:
        """
        POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
        payload includes:
        - body: review summary markdown
        - event: e.g. "COMMENT"
        - comments: list of {path, body, line, side} items
          (We use 'line' on the 'RIGHT' side of the diff. For partial failures,
           GitHub rejects the whole request; caller should fall back to a single comment.)
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pull_number}/reviews"
        payload = {"body": body, "event": event, "comments": comments}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()
