from typing import List, Dict
import httpx


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def list_pr_files(self, repo: str, pr_number: int) -> List[Dict]:
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
        files: List[Dict] = []
        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while True:
                r = await client.get(
                    url, headers=self._headers(), params={"per_page": 100, "page": page}
                )
                r.raise_for_status()
                chunk = r.json()
                files.extend(chunk)
                if len(chunk) < 100:
                    break
                page += 1
        return files

    async def post_issue_comment(self, repo: str, issue_number: int, body: str) -> Dict:
        # PRs are issues under the hood; this posts a single top-level comment to the PR
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=self._headers(), json={"body": body})
            r.raise_for_status()
            return r.json()

    async def add_labels(self, repo: str, issue_number: int, labels: List[str]) -> Dict:
        """
        Add labels to an issue/PR. `repo` is 'owner/name'.
        """
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/labels"
        headers = self._headers()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url, headers=headers, json={"labels": labels}, timeout=30.0
            )
            r.raise_for_status()
            return r.json()
