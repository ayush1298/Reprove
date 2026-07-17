"""GitHub webhook normalization. Delivery verification stays at the API edge."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GitHubTrigger:
    kind: str
    repository: str
    issue_number: int | None
    claim: str
    installation_id: str | None


def normalize_trigger(event: str, payload: dict) -> GitHubTrigger | None:
    repository = payload.get("repository", {}).get("full_name")
    if not repository:
        return None
    installation_id = str(payload.get("installation", {}).get("id")) if payload.get("installation", {}).get("id") else None
    if event == "issues" and payload.get("action") == "labeled" and payload.get("label", {}).get("name") == "reprove":
        issue = payload.get("issue", {})
        return GitHubTrigger("issue_prover", repository, issue.get("number"), issue.get("body") or issue.get("title") or "", installation_id)
    if event == "issue_comment" and payload.get("action") == "created" and "@reprove reproduce this" in payload.get("comment", {}).get("body", "").lower():
        issue = payload.get("issue", {})
        return GitHubTrigger("issue_prover", repository, issue.get("number"), issue.get("body") or issue.get("title") or "", installation_id)
    if event == "pull_request" and payload.get("action") in {"opened", "synchronize", "reopened"} and payload.get("pull_request", {}).get("user", {}).get("type") == "Bot":
        pull = payload.get("pull_request", {})
        return GitHubTrigger("ai_pr_audit", repository, pull.get("number"), pull.get("title") or "AI pull request", installation_id)
    return None
