"""Domain types. Verdicts are deliberately distinct: uncertainty is evidence too."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Verdict(str, Enum):
    REPRODUCED = "REPRODUCED"
    CANNOT_REPRODUCE = "CANNOT_REPRODUCE"
    NEEDS_INFO = "NEEDS_INFO"
    ENV_UNSUPPORTED = "ENV_UNSUPPORTED"
    NOT_A_BUG = "NOT_A_BUG"
    FIX_VERIFIED = "FIX_VERIFIED"
    FIX_REJECTED = "FIX_REJECTED"


class Gate(str, Enum):
    BOOTSTRAP = "bootstrap"
    FAIL_ON_MAIN = "fail_on_main"
    PASS_AFTER_FIX = "pass_after_fix"
    ANTI_CHEAT = "anti_cheat"
    MUTATION = "mutation"
    BLAST_RADIUS = "blast_radius"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BOOTSTRAPPING = "bootstrapping"
    GENERATING_EVIDENCE = "generating_evidence"
    VERIFYING = "verifying"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass(slots=True)
class GateResult:
    gate: Gate
    passed: bool
    summary: str
    runs: list[CommandResult] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceBundle:
    repository: str
    claim: str
    verdict: Verdict
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    tests: list[str] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)
    narrative: str = ""
    confidence: int = 0
    warnings: list[str] = field(default_factory=list)
    proposed_questions: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    def gate(self, gate: Gate) -> GateResult | None:
        return next((item for item in self.gates if item.gate == gate), None)

    def add(self, result: GateResult) -> GateResult:
        self.gates.append(result)
        return result

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BootstrapPlan:
    ecosystem: str | None
    install: list[str] | None
    test: list[str] | None
    source: str
    supported: bool
    reason: str = ""


@dataclass(slots=True)
class ChangeSet:
    """A proposed fix represented before it is allowed to touch the checkout."""

    files: dict[str, str]
    description: str
    author: str = "agent"

    def paths(self) -> list[Path]:
        return [Path(path) for path in self.files]
