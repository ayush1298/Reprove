from reprove.github import GitHubClient
from reprove.models import EvidenceBundle, Verdict
from reprove.publication import EvidencePublisher, PublicationRequest


class RecordingGitHub(GitHubClient):
    def __init__(self):
        super().__init__("acme/demo", "token")
        self.calls = []

    def _request(self, method, endpoint, body=None):
        self.calls.append((method, endpoint, body))
        if endpoint.startswith("/git/ref"):
            return {"object": {"sha": "base"}}
        return {"ok": True}


def test_verified_fix_publishes_evidence_and_draft_pr():
    client = RecordingGitHub()
    bundle = EvidenceBundle("acme/demo", "Bug", Verdict.FIX_VERIFIED, confidence=100)
    result = EvidencePublisher().publish(client, bundle, PublicationRequest(7, "reprove/issue-7", "main", {"tests/test_bug.py": "assert False\n"}, "Fix bug"))
    endpoints = [call[1] for call in client.calls]
    assert "/issues/7/comments" in endpoints
    assert "/check-runs" in endpoints
    assert "/pulls" in endpoints
    assert result["pull_request"] == {"ok": True}
