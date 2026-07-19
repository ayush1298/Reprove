import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from reprove.api import create_app


def _repo(client: TestClient) -> dict:
    client.post("/v1/organizations", json={"slug": "integrations", "name": "Integrations"})
    return client.post("/v1/repositories", json={"organization_slug": "integrations", "full_name": "integrations/demo"}).json()


def test_incident_intake_can_be_attached_to_a_real_evidence_run(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (tmp_path / "feature.py").write_text("def allowed(value):\n    return value > 5\n")
    tests = tmp_path / "tests"; tests.mkdir()
    (tests / "test_feature.py").write_text("from feature import allowed\n\ndef test_boundary():\n    assert allowed(5)\n")
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        repo = _repo(client)
        intake = client.post("/v1/integrations/intake", json={"provider": "sentry", "external_ref": "PROJ-42", "title": "Boundary crash", "claim": "Boundary must be inclusive", "repository_id": repo["id"], "fingerprint": "boundary"})
        assert intake.status_code == 201
        started = client.post(f"/v1/integrations/{intake.json()['id']}/evidence-run", json={"repository_id": repo["id"], "repository_path": str(tmp_path), "claim": "Boundary must be inclusive", "evidence_tests": ["tests/test_feature.py"], "test_command": ["python", "-m", "pytest", "tests/test_feature.py"]})
        assert started.status_code == 202
        run_id = started.json()["id"]
        for _ in range(200):
            run = client.get(f"/v1/runs/{run_id}").json()
            if run.get("status") in {"completed", "failed"}:
                break
            time.sleep(.03)
        assert run["status"] == "completed"
        ledger = client.get("/v1/ledger", params={"repository_id": repo["id"]}).json()
        assert ledger["summary"]["bundles"] == 1
        assert ledger["integrations"][0]["status"] == "resolved"


def test_pr_check_and_mcp_audit_never_publish(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        repo = _repo(client)
        checked = client.post("/v1/integrations/github/pr-check", json={"repository_id": repo["id"], "pull_request_number": 15, "linked_issue": False, "unified_diff": "-assert response.status_code == 200\n", "regression_clean": False})
        assert checked.status_code == 201
        assert checked.json()["status"] == "needs_review"
        tools = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list"})
        assert tools.status_code == 200
        assert {tool["name"] for tool in tools.json()["result"]["tools"]} == {"reprove_audit_pr", "reprove_replay_bundle", "reprove_ledger"}
        audit = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "reprove_audit_pr", "arguments": {"linked_issue": False, "unified_diff": "", "regression_clean": True}}})
        body = json.loads(audit.json()["result"]["content"][0]["text"])
        assert body["decision"] == "REJECTED"


def test_signed_sentry_webhook_normalizes_without_outbound_write(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROVE_INTEGRATION_WEBHOOK_SECRET", "integration-secret")
    app = create_app("sqlite://", tmp_path / "artifacts")
    payload = {"data": {"issue": {"id": "123", "shortId": "APP-123", "title": "Boom", "permalink": "https://sentry.example/123", "level": "error"}}}
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"integration-secret", raw, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        response = client.post("/v1/integrations/webhooks/sentry", content=raw, headers={"x-reprove-signature": signature})
        assert response.status_code == 202
        assert response.json()["outbound_writes"] is False
        assert response.json()["event"]["title"] == "Boom"
