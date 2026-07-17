from fastapi.testclient import TestClient

from reprove.api import create_app


def test_pr_audit_api_rejects_unproven_or_weakened_change(tmp_path):
    app = create_app("sqlite://", tmp_path / "artifacts")
    with TestClient(app) as client:
        response = client.post("/v1/audits/pull-request", json={"linked_issue": False, "unified_diff": "-assert response.status_code == 200\n", "regression_clean": True})
        assert response.status_code == 200
        assert response.json()["decision"] == "REJECTED"
        assert {item["code"] for item in response.json()["findings"]} == {"missing_issue_link", "missing_evidence", "evidence_weakened"}
