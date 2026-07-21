from fastapi.testclient import TestClient

from reprove.api import create_app


def test_managed_runner_matches_capabilities_and_only_completes_its_lease(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        org = client.post("/v1/organizations", json={"slug": "managed-org", "name": "Managed Org"}).json()
        repo = client.post("/v1/repositories", json={"organization_slug": "managed-org", "full_name": "managed-org/demo", "runner_mode": "managed"}).json()
        created = client.post("/v1/runs/issue-prover", json={"repository_id": repo["id"], "repository_path": "/pinned/checkout", "claim": "A boundary failure is reproducible", "runner_requirements": {"network_isolated": True, "read_only_source": True}}).json()
        weak = client.post("/v1/runners", json={"organization_id": org["id"], "name": "weak", "mode": "managed", "capabilities": {"network_isolated": False, "read_only_source": True}}).json()
        assert client.post(f"/v1/runners/{weak['runner_id']}/leases", headers={"Authorization": f"Bearer {weak['lease_token']}"}).status_code == 204
        runner = client.post("/v1/runners", json={"organization_id": org["id"], "name": "isolated", "mode": "managed", "capabilities": {"network_isolated": True, "read_only_source": True}}).json()
        lease = client.post(f"/v1/runners/{runner['runner_id']}/leases", headers={"Authorization": f"Bearer {runner['lease_token']}"})
        assert lease.status_code == 200
        assert lease.json()["id"] == created["id"]
        bundle = {"repository": "managed-org/demo", "claim": "A boundary failure is reproducible", "verdict": "REPRODUCED", "tests": ["tests/test_boundary.py"], "gates": [], "confidence": 90}
        completed = client.post(f"/v1/runners/{runner['runner_id']}/runs/{created['id']}/complete", headers={"Authorization": f"Bearer {runner['lease_token']}"}, json={"summary": "The pinned test fails on main.", "bundle": bundle})
        assert completed.status_code == 200
        assert completed.json()["verdict"] == "REPRODUCED"
