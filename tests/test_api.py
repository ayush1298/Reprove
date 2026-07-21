import time
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from reprove.api import create_app
from reprove.github import PublicIssue


def _fixture_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (root / "limit.py").write_text("def allows(value):\n    return value > 5\n")
    tests = root / "tests"; tests.mkdir()
    (tests / "test_limit.py").write_text("from limit import allows\n\ndef test_boundary():\n    assert allows(5)\n")


def test_api_persists_and_streams_an_issue_verdict(tmp_path):
    _fixture_repo(tmp_path)
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/v1/organizations", json={"slug": "demo-org", "name": "Demo Org"}).status_code == 201
        repo = client.post("/v1/repositories", json={"organization_slug": "demo-org", "full_name": "demo-org/demo"}).json()
        submitted = client.post("/v1/runs/issue-prover", json={
            "repository_id": repo["id"], "repository_path": str(tmp_path), "claim": "Boundary must be inclusive",
            "evidence_tests": ["tests/test_limit.py"], "test_command": ["python", "-m", "pytest", "tests/test_limit.py"],
        })
        assert submitted.status_code == 202
        run_id = submitted.json()["id"]
        for _ in range(60):
            run = client.get(f"/v1/runs/{run_id}").json()
            if run["status"] in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert run["status"] == "completed"
        assert run["verdict"] == "REPRODUCED"
        assert any(event["type"] == "run.completed" for event in run["events"])
        bundle = client.get(f"/v1/runs/{run_id}/bundle")
        assert bundle.status_code == 200
        assert bundle.json()["verdict"] == "REPRODUCED"
        manifest = tmp_path / "artifacts" / run_id / "manifest.json"
        assert manifest.exists()
        assert len(json.loads(manifest.read_text())["sha256"]) == 64


def test_benchmark_catalog_is_explicitly_read_only(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        response = client.get("/v1/benchmarks")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert "No remote writes" in payload["guarantee"]
    assert all(task["status"] == "candidate" for task in payload["tasks"])


def test_swe_bench_readiness_report_never_claims_an_unrun_score(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        response = client.get("/v1/evaluations/swe-bench")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["report"]["score_status"] == "NOT_RUN"
    assert payload["report"]["intake"]["resolution_rate"] is None
    assert payload["shortlist"]["quarantined"]


def test_public_issue_preview_is_get_only_intake(tmp_path, monkeypatch):
    monkeypatch.setattr("reprove.api.fetch_public_issue", lambda _: PublicIssue(
        repository="pytest-dev/pytest", number=11706, title="Fixture teardown", body="Minimal example", html_url="https://github.com/pytest-dev/pytest/issues/11706",
        state="closed", labels=["type: bug"], author="contributor", updated_at="2024-01-01T00:00:00Z",
    ))
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        response = client.post("/v1/github/issue-preview", json={"issue_url": "https://github.com/pytest-dev/pytest/issues/11706"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["issue"]["repository"] == "pytest-dev/pytest"
    assert [stage["id"] for stage in payload["stages"]] == ["intake", "review", "design", "execute"]
