import time
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from reprove.api import create_app


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
