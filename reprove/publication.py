"""GitHub evidence publication workflow. The caller supplies a short-lived installation token."""

from __future__ import annotations

from dataclasses import dataclass

from .github import GitHubClient
from .models import EvidenceBundle, Verdict
from .reporting import issue_comment, pull_request_body


@dataclass(slots=True)
class PublicationRequest:
    issue_number: int
    branch: str
    base_branch: str
    evidence_files: dict[str, str]
    change_summary: str | None = None


class EvidencePublisher:
    def publish(self, client: GitHubClient, bundle: EvidenceBundle, request: PublicationRequest) -> dict:
        """Publish immutable evidence first; open only a draft PR for a verified source change."""
        branch = client.create_reprove_branch(request.branch, request.base_branch)
        for path, content in request.evidence_files.items():
            client.upsert_text_file(request.branch, path, content, f"reprove: add evidence for issue #{request.issue_number}")
        comment = client.comment_on_issue(request.issue_number, issue_comment(bundle))
        head_sha = client.branch_head(request.branch)
        conclusion = "success" if bundle.verdict in {Verdict.REPRODUCED, Verdict.FIX_VERIFIED} else "neutral"
        check = client.create_check(head_sha, "Reprove evidence", conclusion, bundle.narrative or bundle.verdict.value)
        pull = None
        if request.change_summary and bundle.verdict is Verdict.FIX_VERIFIED:
            pull = client.create_draft_pr(f"reprove: verified fix for #{request.issue_number}", pull_request_body(bundle, request.change_summary), request.branch, request.base_branch)
        return {"branch": branch, "comment": comment, "check": check, "pull_request": pull}
