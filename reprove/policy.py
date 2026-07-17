"""Tiny dependency-free parser for the deliberately small .reprove.yml policy surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass(slots=True)
class Policy:
    autonomy: str = "draft-pr"
    determinism_runs: int = 5
    mutation_count: int = 3
    full_suite_timeout_seconds: int = 300
    protected_paths: list[str] = field(default_factory=lambda: [".github/", "infra/", "secrets/"])
    allowed_commands: list[str] = field(default_factory=list)
    cost_cap_usd: float = 5.0
    runner_mode: Literal["hosted", "self-hosted"] = "hosted"
    branch_prefix: str = "reprove/"

    @classmethod
    def load(cls, root: Path) -> "Policy":
        path = root / ".reprove.yml"
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text()) or {}
        if not isinstance(raw, dict):
            raise ValueError(".reprove.yml must be a mapping.")
        defaults = cls()
        autonomy = str(raw.get("autonomy", defaults.autonomy))
        if autonomy not in {"evidence-only", "draft-pr", "auto-pr"}:
            raise ValueError("autonomy must be evidence-only, draft-pr, or auto-pr.")
        runner_mode = str(raw.get("runner_mode", defaults.runner_mode))
        if runner_mode not in {"hosted", "self-hosted"}:
            raise ValueError("runner_mode must be hosted or self-hosted.")
        policy = cls(
            autonomy=autonomy,
            determinism_runs=int(raw.get("determinism_runs", defaults.determinism_runs)),
            mutation_count=int(raw.get("mutation_count", defaults.mutation_count)),
            full_suite_timeout_seconds=int(raw.get("full_suite_timeout_seconds", defaults.full_suite_timeout_seconds)),
            protected_paths=list(raw.get("protected_paths", defaults.protected_paths)),
            allowed_commands=list(raw.get("allowed_commands", [])),
            cost_cap_usd=float(raw.get("cost_cap_usd", defaults.cost_cap_usd)),
            runner_mode=runner_mode,
            branch_prefix=str(raw.get("branch_prefix", defaults.branch_prefix)),
        )
        if policy.determinism_runs < 1 or policy.determinism_runs > 10:
            raise ValueError("determinism_runs must be between 1 and 10.")
        if policy.mutation_count < 1 or policy.mutation_count > 10:
            raise ValueError("mutation_count must be between 1 and 10.")
        if policy.full_suite_timeout_seconds < 1 or policy.full_suite_timeout_seconds > 3600:
            raise ValueError("full_suite_timeout_seconds must be between 1 and 3600.")
        if policy.cost_cap_usd <= 0:
            raise ValueError("cost_cap_usd must be positive.")
        if not policy.branch_prefix.startswith("reprove/"):
            raise ValueError("branch_prefix must remain within reprove/.")
        return policy

    def as_dict(self) -> dict:
        return asdict(self)
