import sys

from reprove.evidence import determinism_gate, mutation_gate
from reprove.execution import Runner
from reprove.models import Gate
from reprove.policy import Policy


def test_environment_start_failure_is_not_called_a_reproduction(tmp_path):
    gate = determinism_gate(Runner(tmp_path), ["missing-reprove-command"], Policy(determinism_runs=2), should_pass=False)
    assert not gate.passed
    assert gate.details["environment_like"]


def test_vacuous_evidence_fails_the_mutation_gate(tmp_path):
    (tmp_path / "app.py").write_text("def permitted(value):\n    return value == 5\n")
    test = tmp_path / "check.py"
    test.write_text("assert True\n")
    gate = mutation_gate(tmp_path, Runner(tmp_path), [sys.executable, "check.py"], ["app.py"], Policy(mutation_count=1))
    assert gate.gate is Gate.MUTATION
    assert not gate.passed
