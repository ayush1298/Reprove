"""Hard gates that make cheating mechanically impossible, not merely discouraged in a prompt."""

from __future__ import annotations

import re
from pathlib import Path

from .models import ChangeSet, Gate, GateResult
from .policy import Policy

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|(_test|\.test|\.spec)\.(py|js|ts|tsx)$", re.I)
WEAKENING = re.compile(r"(?:pytest\.skip|pytest\.mark\.skip|\.skip\(|\.todo\(|\bassert\s+(?:True|1)\b)", re.M)
ASSERT_REMOVAL = re.compile(r"^-.*\b(assert|expect\(|toEqual\(|toBe\()", re.M)


def is_test_path(path: str | Path) -> bool:
    return bool(TEST_PATH.search(str(path).replace("\\", "/")))


def enforce_fix_boundary(change: ChangeSet, policy: Policy) -> GateResult:
    test_files = [str(path) for path in change.paths() if is_test_path(path)]
    protected = [str(path) for path in change.paths() if any(str(path).startswith(prefix) for prefix in policy.protected_paths)]
    if test_files:
        return GateResult(Gate.ANTI_CHEAT, False, "Rejected: the fix loop may never write test files.", details={"blocked_paths": test_files})
    if protected:
        return GateResult(Gate.ANTI_CHEAT, False, "Rejected: proposed change touches protected paths.", details={"blocked_paths": protected})
    combined = "\n".join(change.files.values())
    if WEAKENING.search(combined) or ASSERT_REMOVAL.search(combined):
        return GateResult(Gate.ANTI_CHEAT, False, "Rejected: assertion weakening or skip marker detected.")
    return GateResult(Gate.ANTI_CHEAT, True, "Fix boundary intact: no test or protected path was modified.")


def lint_unified_diff(diff: str) -> GateResult:
    """Defense in depth for integrations that receive a raw Git diff before apply."""
    if ASSERT_REMOVAL.search(diff):
        return GateResult(Gate.ANTI_CHEAT, False, "Rejected: patch removes an assertion.")
    if WEAKENING.search("\n".join(line[1:] for line in diff.splitlines() if line.startswith("+"))):
        return GateResult(Gate.ANTI_CHEAT, False, "Rejected: patch adds an assertion weakening or skip marker.")
    return GateResult(Gate.ANTI_CHEAT, True, "Patch linter found no assertion weakening.")


def apply_change(root: Path, change: ChangeSet) -> None:
    """Call only after enforce_fix_boundary has passed."""
    for relative, content in change.files.items():
        destination = (root / relative).resolve()
        if root.resolve() not in destination.parents:
            raise ValueError(f"Path escapes repository: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
