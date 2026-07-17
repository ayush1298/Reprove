from fastapi.testclient import TestClient

from reprove.api import create_app


def test_mutating_api_routes_require_configured_bearer_token(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROVE_API_TOKEN", "local-secret")
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        payload = {"slug": "secure-org", "name": "Secure Org"}
        assert client.post("/v1/organizations", json=payload).status_code == 401
        assert client.post("/v1/organizations", json=payload, headers={"Authorization": "Bearer local-secret"}).status_code == 201
