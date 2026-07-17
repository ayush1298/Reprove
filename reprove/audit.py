"""Independent pull-request evidence audit for AI-authored or human-authored changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import EvidenceBundle, Verdict
from .safety import lint_unified_diff


class AuditDecision(str, Enum):
    VERIFIED = "VERIFIED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    REJECTED = "REJECTED"
    WARNING = "WARNING"


@dataclass(slots=True)
class AuditFinding:
    code: str
    message: str
    severity: str


@dataclass(slots=True)
class AuditResult:
    decision: AuditDecision
    findings: list[AuditFinding] = field(default_factory=list)
    confidence: int = 0


def audit_pull_request(*, linked_issue: bool, evidence: EvidenceBundle | None, unified_diff: str, regression_clean: bool) -> AuditResult:
    """Pure, reusable check logic for the future GitHub Check integration."""
    findings: list[AuditFinding] = []
    if not linked_issue:
        findings.append(AuditFinding("missing_issue_link", "The pull request is not linked to a user-visible maintenance claim.", "error"))
    if not evidence:
        findings.append(AuditFinding("missing_evidence", "No Reprove evidence bundle accompanies this pull request.", "error"))
    elif evidence.verdict not in {Verdict.REPRODUCED, Verdict.FIX_VERIFIED}:
        findings.append(AuditFinding("unproven_claim", f"Evidence verdict is {evidence.verdict.value}, not a reproducible claim.", "error"))
    patch_gate = lint_unified_diff(unified_diff)
    if not patch_gate.passed:
        findings.append(AuditFinding("evidence_weakened", patch_gate.summary, "error"))
    if not regression_clean:
        findings.append(AuditFinding("regression_warning", "Regression blast radius is not clean; PR must remain draft.", "warning"))
    if any(finding.severity == "error" for finding in findings):
        return AuditResult(AuditDecision.REJECTED, findings, 0)
    if findings:
        return AuditResult(AuditDecision.WARNING, findings, evidence.confidence if evidence else 0)
    return AuditResult(AuditDecision.VERIFIED, [], evidence.confidence if evidence else 0)
