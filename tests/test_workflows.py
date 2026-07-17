import sys
from pathlib import Path

from reprove.models import ChangeSet, Verdict
from reprove.workflows import IssueProver, ReproductionProposal


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (tmp_path / "limit.py").write_text("def allows(value):\n    return value > 5\n")
    tests = tmp_path / "tests"; tests.mkdir()
    (tests / "test_limit.py").write_text("from limit import allows\n\ndef test_boundary():\n    assert allows(5)\n")
    return tmp_path


def test_issue_prover_reproduces_then_verifies_fix_and_mutation(tmp_path):
    root = _repo(tmp_path)
    command = [sys.executable, "-m", "pytest", "tests/test_limit.py"]
    proposal = ReproductionProposal(["tests/test_limit.py"], command, ["limit.py"], [])
    prover = IssueProver(root)
    bundle = prover.prove("Boundary must be inclusive", proposal)
    assert bundle.verdict is Verdict.REPRODUCED
    fixed = ChangeSet({"limit.py": "def allows(value):\n    return value >= 5\n"}, "Use inclusive boundary")
    bundle = prover.verify_fix(bundle, proposal, fixed, command)
    assert bundle.verdict is Verdict.FIX_VERIFIED
    assert bundle.confidence == 100
    assert "> 5" in (root / "limit.py").read_text()  # source checkout remains untouched


def test_no_test_proposal_requests_targeted_information(tmp_path):
    bundle = IssueProver(_repo(tmp_path)).prove("It does not work", ReproductionProposal([], [], [], ["What input fails?"]))
    assert bundle.verdict is Verdict.NEEDS_INFO
    assert bundle.proposed_questions == ["What input fails?"]


def test_documented_behavior_gets_a_distinct_not_a_bug_verdict(tmp_path):
    root = _repo(tmp_path)
    command = [sys.executable, "-m", "pytest", "tests/test_limit.py"]
    # The candidate test happens to pass after the source is adjusted locally;
    # this exercises the explicit documented-intent classification branch.
    (root / "limit.py").write_text("def allows(value):\n    return value >= 5\n")
    proposal = ReproductionProposal(["tests/test_limit.py"], command, [], [], documented_intent_matches=True)
    assert IssueProver(root).prove("Documented inclusive boundary", proposal).verdict is Verdict.NOT_A_BUG
