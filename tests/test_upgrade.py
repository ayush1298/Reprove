import sys
from pathlib import Path

from reprove.models import ChangeSet, Verdict
from reprove.workflows import UpgradeProposal, UpgradeVerifier


def test_upgrade_canary_exposes_a_silent_behavior_change(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (tmp_path / "compat.py").write_text("def empty():\n    return {}\n")
    tests = tmp_path / "tests"; tests.mkdir()
    (tests / "test_canary.py").write_text("from compat import empty\n\ndef test_old_contract():\n    assert empty() == {}\n")
    proposal = UpgradeProposal("parser", "1", "2", ChangeSet({"compat.py": "def empty():\n    return None\n"}, "bump"), ["tests/test_canary.py"], [sys.executable, "-m", "pytest", "tests/test_canary.py"])
    bundle = UpgradeVerifier(tmp_path).verify(proposal)
    assert bundle.verdict is Verdict.REPRODUCED
    assert bundle.gate(next(g.gate for g in bundle.gates if g.gate.value == "fail_on_main")).passed
    assert "return {}" in (tmp_path / "compat.py").read_text()
