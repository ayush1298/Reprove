"""Minimal GitHub REST adapter. It is opt-in and only creates reprove/* branches."""

from __future__ import annotations

import json
import base64
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(slots=True)
class GitHubClient:
    repository: str
    token: str
    api_url: str = "https://api.github.com"

    def _request(self, method: str, endpoint: str, body: dict | None = None) -> dict:
        payload = json.dumps(body).encode() if body is not None else None
        request = Request(f"{self.api_url}/repos/{self.repository}{endpoint}", data=payload, method=method, headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}", "X-GitHub-Api-Version": "2022-11-28", **({"Content-Type": "application/json"} if payload else {})})
        with urlopen(request, timeout=20) as response:  # nosec B310: fixed GitHub API origin
            return json.loads(response.read())

    def comment_on_issue(self, issue_number: int, body: str) -> dict:
        return self._request("POST", f"/issues/{issue_number}/comments", {"body": body})

    def branch_head(self, branch: str = "main") -> str:
        return self._request("GET", f"/git/ref/heads/{branch}")["object"]["sha"]

    def create_branch(self, branch: str, sha: str) -> dict:
        if not branch.startswith("reprove/"):
            raise ValueError("Reprove may create branches only under reprove/*.")
        return self._request("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})

    def create_reprove_branch(self, branch: str, base_branch: str = "main") -> dict:
        return self.create_branch(branch, self.branch_head(base_branch))

    def upsert_text_file(self, branch: str, path: str, content: str, message: str, sha: str | None = None) -> dict:
        if not branch.startswith("reprove/"):
            raise ValueError("Reprove may write files only to reprove/* branches.")
        body = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": branch}
        if sha:
            body["sha"] = sha
        return self._request("PUT", f"/contents/{path}", body)

    def create_check(self, head_sha: str, name: str, conclusion: str | None, summary: str, details_url: str | None = None) -> dict:
        body = {"name": name, "head_sha": head_sha, "status": "completed" if conclusion else "in_progress", "output": {"title": name, "summary": summary}}
        if conclusion:
            body["conclusion"] = conclusion
        if details_url:
            body["details_url"] = details_url
        return self._request("POST", "/check-runs", body)

    def create_draft_pr(self, title: str, body: str, head: str, base: str = "main") -> dict:
        if not head.startswith("reprove/"):
            raise ValueError("Reprove may open pull requests only from reprove/* branches.")
        return self._request("POST", "/pulls", {"title": title, "body": body, "head": head, "base": base, "draft": True})


@dataclass(frozen=True, slots=True)
class PublicIssue:
    """Public issue data obtained with a single anonymous GET request."""

    repository: str
    number: int
    title: str
    body: str
    html_url: str
    state: str
    labels: list[str]
    author: str | None
    updated_at: str | None


def parse_public_issue_url(issue_url: str) -> tuple[str, int]:
    """Accept only canonical public GitHub issue URLs, never pull-request URLs."""
    parsed = urlparse(issue_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or parsed.netloc != "github.com" or len(parts) != 4 or parts[2] != "issues" or not parts[3].isdigit():
        raise ValueError("Use a public GitHub issue URL such as https://github.com/owner/repo/issues/123.")
    return f"{parts[0]}/{parts[1]}", int(parts[3])


def fetch_public_issue(issue_url: str, api_url: str = "https://api.github.com") -> PublicIssue:
    """Fetch an issue with GET only; it sends no credential and has no write path."""
    repository, number = parse_public_issue_url(issue_url)
    request = Request(
        f"{api_url}/repos/{repository}/issues/{number}",
        method="GET",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "reprove-read-only-intake"},
    )
    try:
        with urlopen(request, timeout=12) as response:  # nosec B310: fixed GitHub API origin
            payload = json.loads(response.read())
    except HTTPError as error:
        if error.code == 404:
            raise ValueError("Issue was not found or is not public.") from error
        raise ValueError(f"GitHub returned HTTP {error.code} while reading the issue.") from error
    except URLError as error:
        raise ValueError("Could not reach GitHub. Check your connection and try again.") from error
    if "pull_request" in payload:
        raise ValueError("This URL resolves to a pull request; provide a GitHub issue instead.")
    return PublicIssue(
        repository=repository, number=number, title=payload.get("title") or f"Issue #{number}", body=payload.get("body") or "",
        html_url=payload.get("html_url") or issue_url, state=payload.get("state") or "unknown",
        labels=[label.get("name", "") for label in payload.get("labels", []) if label.get("name")],
        author=payload.get("user", {}).get("login"), updated_at=payload.get("updated_at"),
    )
