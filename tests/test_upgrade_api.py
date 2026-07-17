import time

from fastapi.testclient import TestClient

from reprove.api import create_app


def test_upgrade_api_finds_a_canary_flip(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (tmp_path / "compat.py").write_text("def empty():\n    return {}\n")
    tests = tmp_path / "tests"; tests.mkdir()
    (tests / "test_canary.py").write_text("from compat import empty\n\ndef test_old_contract():\n    assert empty() == {}\n")
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        client.post("/v1/organizations", json={"slug": "demo-org", "name": "Demo Org"})
        repo = client.post("/v1/repositories", json={"organization_slug": "demo-org", "full_name": "demo-org/upgrade"}).json()
        response = client.post("/v1/runs/upgrade-verifier", json={"repository_id": repo["id"], "repository_path": str(tmp_path), "dependency": "parser", "old_version": "1", "new_version": "2", "files": {"compat.py": "def empty():\n    return None\n"}, "canary_tests": ["tests/test_canary.py"], "canary_command": ["python", "-m", "pytest", "tests/test_canary.py"]})
        run_id = response.json()["id"]
        for _ in range(60):
            run = client.get(f"/v1/runs/{run_id}").json()
            if run["status"] in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert run["status"] == "completed"
        assert run["verdict"] == "REPRODUCED"
