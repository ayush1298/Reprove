from reprove.github import GitHubClient


class FakeGitHub(GitHubClient):
    def __init__(self):
        super().__init__("acme/demo", "token")
        self.calls = []

    def _request(self, method, endpoint, body=None):
        self.calls.append((method, endpoint, body))
        return {"object": {"sha": "base-sha"}}


def test_evidence_branch_uses_restricted_prefix_and_base_head():
    client = FakeGitHub()
    client.create_reprove_branch("reprove/issue-7", "trunk")
    assert client.calls == [("GET", "/git/ref/heads/trunk", None), ("POST", "/git/refs", {"ref": "refs/heads/reprove/issue-7", "sha": "base-sha"})]


def test_upsert_requires_reprove_branch():
    client = FakeGitHub()
    try:
        client.upsert_text_file("main", "tests/evidence.py", "assert False", "evidence")
    except ValueError as error:
        assert "reprove" in str(error)
    else:
        raise AssertionError("main write was not blocked")
