from fastapi.testclient import TestClient

from reprove.api import create_app


def test_webhook_delivery_is_idempotent(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    payload = {"action": "labeled", "label": {"name": "reprove"}, "repository": {"full_name": "acme/demo"}, "issue": {"number": 5, "title": "Bug"}}
    with TestClient(app) as client:
        headers = {"x-github-event": "issues", "x-github-delivery": "delivery-1"}
        first = client.post("/v1/github/webhooks", json=payload, headers=headers)
        again = client.post("/v1/github/webhooks", json=payload, headers=headers)
        assert first.json()["trigger"] == "issue_prover"
        assert again.json()["duplicate"] is True


def test_actionable_webhook_creates_review_only_intake_for_connected_repo(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        org = client.post("/v1/organizations", json={"slug": "acme", "name": "Acme"}).json()
        repo = client.post("/v1/repositories", json={"organization_slug": "acme", "full_name": "acme/demo", "runner_mode": "managed"}).json()
        payload = {"action": "labeled", "label": {"name": "reprove"}, "installation": {"id": 99}, "repository": {"full_name": "acme/demo"}, "issue": {"number": 5, "title": "Boundary bug", "body": "Five should be valid"}}
        response = client.post("/v1/github/webhooks", json=payload, headers={"x-github-event": "issues", "x-github-delivery": "delivery-2"})
        assert response.status_code == 202
        assert response.json()["routing"] == "awaiting_review"
        run = client.get(f"/v1/runs/{response.json()['run_id']}").json()
        assert run["status"] == "awaiting_review"
        assert run["source"]["installation_id"] == "99"
        assert repo["id"] == run["repository_id"]
