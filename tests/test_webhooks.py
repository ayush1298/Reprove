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
