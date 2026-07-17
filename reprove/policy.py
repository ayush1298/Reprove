"""Tiny dependency-free parser for the deliberately small .reprove.yml policy surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Policy:
    autonomy: str = "draft-pr"
    determinism_runs: int = 5
    mutation_count: int = 3
    full_suite_timeout_seconds: int = 300
    protected_paths: list[str] = field(default_factory=lambda: [".github/", "infra/", "secrets/"])

    @classmethod
    def load(cls, root: Path) -> "Policy":
        path = root / ".reprove.yml"
        if not path.exists():
            return cls()
        values: dict[str, str] = {}
        protected: list[str] = []
        active_list: str | None = None
        for raw in path.read_text().splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if line.lstrip().startswith("-") and active_list == "protected_paths":
                protected.append(line.split("-", 1)[1].strip().strip('"\''))
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                active_list = key.strip()
                values[active_list] = value.strip().strip('"\'')
        return cls(
            autonomy=values.get("autonomy", "draft-pr"),
            determinism_runs=int(values.get("determinism_runs", 5)),
            mutation_count=int(values.get("mutation_count", 3)),
            full_suite_timeout_seconds=int(values.get("full_suite_timeout_seconds", 300)),
            protected_paths=protected or cls().protected_paths,
        )
