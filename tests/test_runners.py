from fastapi.testclient import TestClient

from reprove.api import create_app


def test_self_hosted_runner_registers_and_heartbeats(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        organization = client.post("/v1/organizations", json={"slug": "acme", "name": "Acme"}).json()
        registration = client.post("/v1/runners", json={"organization_id": organization["id"], "name": "acme-linux", "capabilities": {"python": "3.12"}})
        assert registration.status_code == 201
        value = registration.json()
        heartbeat = client.post(f"/v1/runners/{value['runner_id']}/heartbeat", headers={"Authorization": f"Bearer {value['lease_token']}"})
        assert heartbeat.status_code == 200
        repo = client.post("/v1/repositories", json={"organization_slug": "acme", "full_name": "acme/demo", "runner_mode": "self-hosted"}).json()
        client.post("/v1/runs/issue-prover", json={"repository_id": repo["id"], "repository_path": str(tmp_path / "missing"), "claim": "Claim", "evidence_tests": ["tests/test.py"], "test_command": ["pytest"]})
        lease = client.post(f"/v1/runners/{value['runner_id']}/leases", headers={"Authorization": f"Bearer {value['lease_token']}"})
        assert lease.status_code == 200
        assert lease.json()["status"] == "running"
