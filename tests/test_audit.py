from reprove.audit import AuditDecision, audit_pull_request
from reprove.models import EvidenceBundle, Verdict


def test_audit_rejects_removed_assertion_even_with_evidence():
    evidence = EvidenceBundle("demo", "claim", Verdict.REPRODUCED, confidence=80)
    result = audit_pull_request(linked_issue=True, evidence=evidence, unified_diff="-assert response.status_code == 200\n", regression_clean=True)
    assert result.decision is AuditDecision.REJECTED
    assert result.findings[0].code == "evidence_weakened"


def test_audit_marks_clean_proven_pr_verified():
    evidence = EvidenceBundle("demo", "claim", Verdict.FIX_VERIFIED, confidence=100)
    result = audit_pull_request(linked_issue=True, evidence=evidence, unified_diff="+return value >= 5\n", regression_clean=True)
    assert result.decision is AuditDecision.VERIFIED
