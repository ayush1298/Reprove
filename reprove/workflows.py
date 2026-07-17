"""Issue-prover and upgrade-verifier orchestration.

The generator is intentionally pluggable: model output is a *proposal*, and only the
execution gates below are allowed to turn it into evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bootstrap import detect_bootstrap
from .evidence import blast_radius_gate, confidence_score, determinism_gate, mutation_gate, write_bundle
from .execution import Runner, isolated_checkout
from .models import ChangeSet, EvidenceBundle, Gate, GateResult, Verdict
from .policy import Policy
from .reporting import issue_comment, pull_request_body
from .safety import apply_change, enforce_fix_boundary


@dataclass(slots=True)
class ReproductionProposal:
    tests: list[str]
    test_command: list[str]
    localized_files: list[str]
    questions: list[str]
    documented_intent_matches: bool = False


class IssueProver:
    def __init__(self, root: Path, policy: Policy | None = None):
        self.root = root.resolve()
        self.policy = policy or Policy.load(root)
        self.runner = Runner(self.root)

    def prove(self, claim: str, proposal: ReproductionProposal) -> EvidenceBundle:
        plan = detect_bootstrap(self.root)
        bundle = EvidenceBundle(str(self.root), claim, Verdict.CANNOT_REPRODUCE, tests=proposal.tests)
        if not plan.supported:
            bundle.verdict = Verdict.ENV_UNSUPPORTED
            bundle.narrative = plan.reason
            bundle.add(GateResult(Gate.BOOTSTRAP, False, f"Unsupported environment ({plan.source}): {plan.reason}"))
            bundle.confidence = confidence_score(bundle)
            return bundle
        bundle.add(GateResult(Gate.BOOTSTRAP, True, f"Bootstrap inferred from {plan.source} ({plan.ecosystem})."))
        if not proposal.tests or not proposal.test_command:
            bundle.verdict = Verdict.NEEDS_INFO
            bundle.proposed_questions = proposal.questions or ["What exact input and observed output demonstrate the problem?"]
            bundle.narrative = "The report lacks a runnable scenario; no evidence test was generated."
            bundle.confidence = confidence_score(bundle)
            return bundle
        failing = determinism_gate(self.runner, proposal.test_command, self.policy, should_pass=False)
        bundle.add(failing)
        if failing.passed:
            bundle.verdict = Verdict.REPRODUCED
            bundle.narrative = "The reported behavior is pinned by a native test that fails consistently on the current checkout."
        elif failing.details.get("environment_like"):
            bundle.verdict = Verdict.ENV_UNSUPPORTED
            bundle.narrative = "Evidence execution could not start reliably; this is not reported as a reproduction failure."
        else:
            bundle.verdict = Verdict.NOT_A_BUG if proposal.documented_intent_matches else Verdict.CANNOT_REPRODUCE
            bundle.narrative = "Observed behavior matches the documented contract." if proposal.documented_intent_matches else "Candidate evidence did not fail deterministically on the current checkout."
        bundle.confidence = confidence_score(bundle)
        return bundle

    def verify_fix(self, bundle: EvidenceBundle, proposal: ReproductionProposal, change: ChangeSet, nearby_command: list[str] | None = None) -> EvidenceBundle:
        if bundle.verdict != Verdict.REPRODUCED:
            bundle.verdict = Verdict.FIX_REJECTED
            bundle.warnings.append("Fix loop refused: no deterministic failing evidence exists.")
            return bundle
        safety = enforce_fix_boundary(change, self.policy)
        bundle.add(safety)
        if not safety.passed:
            bundle.verdict = Verdict.FIX_REJECTED
            bundle.confidence = confidence_score(bundle)
            return bundle
        # Source changes are applied only inside a throwaway checkout. The host
        # repository retains the failing evidence until a human accepts the PR.
        with isolated_checkout(self.root) as sandbox_root:
            sandbox_runner = Runner(sandbox_root)
            apply_change(sandbox_root, change)
            after = determinism_gate(sandbox_runner, proposal.test_command, self.policy, should_pass=True)
            bundle.add(after)
            if not after.passed:
                bundle.verdict = Verdict.FIX_REJECTED
                bundle.warnings.append("Fix did not make evidence pass consistently.")
                bundle.confidence = confidence_score(bundle)
                return bundle
            bundle.add(mutation_gate(sandbox_root, sandbox_runner, proposal.test_command, list(change.files), self.policy))
            bundle.add(blast_radius_gate(sandbox_runner, nearby_command, self.policy.full_suite_timeout_seconds))
        bundle.verdict = Verdict.FIX_VERIFIED if all(g.passed for g in bundle.gates if g.gate != Gate.BOOTSTRAP) else Verdict.FIX_REJECTED
        if bundle.verdict == Verdict.FIX_VERIFIED:
            bundle.narrative = "Fix satisfies execution evidence and survived the verification gates."
        else:
            bundle.warnings.append("A reliability gate did not pass. Keep this change as a draft for human review.")
        bundle.confidence = confidence_score(bundle)
        return bundle

    def publish_local_artifacts(self, bundle: EvidenceBundle, change: ChangeSet | None = None, issue_number: int | None = None) -> Path:
        target = self.root / ".reprove" / (f"issue-{issue_number}" if issue_number else "run")
        write_bundle(bundle, target)
        (target / "issue-comment.md").write_text(issue_comment(bundle))
        if change:
            (target / "pull-request.md").write_text(pull_request_body(bundle, change.description))
        return target


@dataclass(slots=True)
class UpgradeProposal:
    dependency: str
    old_version: str
    new_version: str
    bump: ChangeSet
    canary_tests: list[str]
    canary_command: list[str]
    changelog_notes: str = ""


class UpgradeVerifier:
    """A verification module, not a general migration engine: canaries expose silent breaks."""

    def __init__(self, root: Path, policy: Policy | None = None):
        self.issue_prover = IssueProver(root, policy)

    def verify(self, proposal: UpgradeProposal, nearby_command: list[str] | None = None) -> EvidenceBundle:
        claim = f"Upgrading {proposal.dependency} from {proposal.old_version} to {proposal.new_version} preserves pinned behavior."
        bundle = EvidenceBundle(str(self.issue_prover.root), claim, Verdict.CANNOT_REPRODUCE, tests=proposal.canary_tests)
        safety = enforce_fix_boundary(proposal.bump, self.issue_prover.policy)
        bundle.add(safety)
        if not safety.passed:
            bundle.verdict = Verdict.FIX_REJECTED
            bundle.confidence = confidence_score(bundle)
            return bundle
        with isolated_checkout(self.issue_prover.root) as sandbox_root:
            sandbox_runner = Runner(sandbox_root)
            # Canary tests must describe old behavior and pass before the bump.
            before = determinism_gate(sandbox_runner, proposal.canary_command, self.issue_prover.policy, should_pass=True)
            bundle.add(before)
            if not before.passed:
                bundle.verdict = Verdict.ENV_UNSUPPORTED if before.details.get("environment_like") else Verdict.NEEDS_INFO
                bundle.narrative = "Canary baseline is not stable; upgrade evidence cannot be trusted."
                bundle.confidence = confidence_score(bundle)
                return bundle
            apply_change(sandbox_root, proposal.bump)
            flipped = determinism_gate(sandbox_runner, proposal.canary_command, self.issue_prover.policy, should_pass=False)
            bundle.add(GateResult(Gate.FAIL_ON_MAIN, flipped.passed, "Canary flipped under the new dependency version; silent behavior change made visible." if flipped.passed else "No pinned canary flipped under the upgrade.", flipped.runs))
            bundle.add(blast_radius_gate(sandbox_runner, nearby_command, self.issue_prover.policy.full_suite_timeout_seconds))
        bundle.verdict = Verdict.REPRODUCED if flipped.passed else Verdict.NOT_A_BUG
        bundle.narrative = proposal.changelog_notes or ("Upgrade changed a behavior that existing tests did not cover." if flipped.passed else "No tested behavior changed under this upgrade.")
        bundle.confidence = confidence_score(bundle)
        return bundle
