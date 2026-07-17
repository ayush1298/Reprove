"""Execution-backed reliability gates and objective confidence scoring."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .execution import Runner
from .models import CommandResult, EvidenceBundle, Gate, GateResult
from .policy import Policy


def determinism_gate(runner: Runner, command: list[str], policy: Policy, should_pass: bool) -> GateResult:
    runs = [runner.run(command) for _ in range(policy.determinism_runs)]
    outcomes = [run.passed for run in runs]
    environment_like = any(run.returncode in (126, 127) or "No module named" in run.stderr or "not found" in run.stderr.lower() or "no such file" in run.stderr.lower() for run in runs)
    if environment_like:
        return GateResult(Gate.PASS_AFTER_FIX if should_pass else Gate.FAIL_ON_MAIN, False, "Environment error detected; this is not a reproduction failure.", runs, {"environment_like": True})
    expected = all(outcomes) if should_pass else not any(outcomes)
    state = "passed" if should_pass else "failed"
    if expected:
        return GateResult(Gate.PASS_AFTER_FIX if should_pass else Gate.FAIL_ON_MAIN, True, f"Evidence test {state} deterministically ({len(runs)}/{len(runs)} runs).", runs)
    detail = f"Non-deterministic: expected {state} on every run, got {[run.passed for run in runs]}."
    return GateResult(Gate.PASS_AFTER_FIX if should_pass else Gate.FAIL_ON_MAIN, False, detail, runs, {"environment_like": False})


def blast_radius_gate(runner: Runner, command: list[str] | None, timeout_seconds: int) -> GateResult:
    if not command:
        return GateResult(Gate.BLAST_RADIUS, False, "No neighboring regression selector available; draft only.")
    result = runner.run(command, timeout_seconds)
    return GateResult(Gate.BLAST_RADIUS, result.passed, "Neighboring regression tests are green." if result.passed else "Neighboring regression tests failed; output must remain a draft.", [result])


MUTATIONS = (("==", "!="), ("!=", "=="), ("<=", "<"), (">=", ">"), ("True", "False"), ("False", "True"), ("+ 1", "- 1"), ("- 1", "+ 1"))


def _micro_mutants(content: str, count: int) -> list[str]:
    mutants: list[str] = []
    for before, after in MUTATIONS:
        if before in content:
            mutants.append(content.replace(before, after, 1))
        if len(mutants) >= count:
            break
    return mutants


def mutation_gate(root: Path, runner: Runner, evidence_command: list[str], changed_paths: list[str], policy: Policy) -> GateResult:
    """Mutate only production files, restoring each byte before the next run."""
    attempts: list[CommandResult] = []
    caught = 0
    total = 0
    for relative in changed_paths:
        source = root / relative
        if not source.exists() or source.suffix not in {".py", ".js", ".ts", ".tsx"}:
            continue
        original = source.read_text()
        for mutant in _micro_mutants(original, policy.mutation_count - total):
            total += 1
            source.write_text(mutant)
            result = runner.run(evidence_command)
            attempts.append(result)
            if not result.passed:
                caught += 1
            source.write_text(original)
            if total >= policy.mutation_count:
                break
        if total >= policy.mutation_count:
            break
    if total == 0:
        return GateResult(Gate.MUTATION, False, "No safe micro-mutation site found in the changed production region; evidence requires review.")
    passed = caught == total
    return GateResult(Gate.MUTATION, passed, f"Evidence killed {caught}/{total} micro-mutations." if passed else f"Evidence killed only {caught}/{total} micro-mutations; possible vacuous test.", attempts, {"killed": caught, "total": total})


def confidence_score(bundle: EvidenceBundle) -> int:
    weights = {Gate.FAIL_ON_MAIN: 30, Gate.PASS_AFTER_FIX: 25, Gate.ANTI_CHEAT: 15, Gate.MUTATION: 20, Gate.BLAST_RADIUS: 10}
    score = sum(weights.get(item.gate, 0) for item in bundle.gates if item.passed)
    # More independent facets add evidence, but confidence is never a model estimate.
    score += min(10, max(0, len(bundle.tests) - 1) * 5)
    return min(100, score)


def write_bundle(bundle: EvidenceBundle, output_dir: Path) -> Path:
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "evidence.json"
    path.write_text(json.dumps(bundle.as_dict(), indent=2, default=str) + "\n")
    return path
