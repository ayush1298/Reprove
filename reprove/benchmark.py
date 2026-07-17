"""Read-only benchmark intake, execution, and reporting.

This module deliberately has no GitHub client and no publication capability. A
benchmark run operates only on two caller-provided local directories: a pinned
pre-fix checkout and a pinned gold checkout. It never creates branches, PRs,
comments, commits, or remote writes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .execution import Runner


READ_ONLY_GUARANTEE = "No remote writes: no branches, commits, pull requests, comments, labels, or issue updates."


@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    """A pinned, auditable task. ``candidate`` entries cannot be executed."""

    id: str
    repository: str
    issue_url: str
    title: str
    source_commit: str | None = None
    gold_commit: str | None = None
    buggy_path: str | None = None
    gold_path: str | None = None
    command: list[str] = field(default_factory=list)
    repetitions: int = 3
    license: str = "UNKNOWN"
    status: str = "candidate"  # candidate | ready
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BenchmarkTask":
        allowed = {field.name for field in __import__("dataclasses").fields(cls)}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"Unknown benchmark task fields: {', '.join(sorted(unknown))}")
        task = cls(**raw)
        task.validate()
        return task

    def validate(self) -> None:
        if not self.id or any(char.isspace() for char in self.id):
            raise ValueError("Task id must be a non-empty, whitespace-free identifier.")
        if not self.repository.startswith("https://github.com/"):
            raise ValueError("Repository must be a public GitHub HTTPS URL.")
        if not self.issue_url.startswith(self.repository + "/issues/"):
            raise ValueError("Issue URL must belong to the declared repository.")
        if self.repetitions < 1 or self.repetitions > 10:
            raise ValueError("Repetitions must be between 1 and 10.")
        if self.status not in {"candidate", "ready"}:
            raise ValueError("Status must be candidate or ready.")
        if self.status == "ready":
            required = (self.source_commit, self.gold_commit, self.buggy_path, self.gold_path, self.command)
            if not all(required):
                raise ValueError("Ready tasks require pinned commits, local paths, and a test command.")


@dataclass(slots=True)
class BenchmarkResult:
    task_id: str
    verdict: str
    reproduced: bool
    valid_under_gold_patch: bool
    deterministic: bool
    source_unchanged: bool
    duration_ms: int
    repetitions: int
    buggy_exit_codes: list[int]
    gold_exit_code: int | None
    read_only: bool = True
    guarantee: str = READ_ONLY_GUARANTEE


def load_manifest(path: Path) -> list[BenchmarkTask]:
    """Read a JSONL manifest with no network access or side effects."""
    tasks: list[BenchmarkTask] = []
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip() and not line.lstrip().startswith("#"):
            try:
                tasks.append(BenchmarkTask.from_dict(json.loads(line)))
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(f"{path}:{line_no}: {error}") from error
    ids = [task.id for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Benchmark task ids must be unique.")
    return tasks


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _copy_read_only(source: Path, target: Path) -> None:
    ignored = shutil.ignore_patterns(".git", ".reprove", "__pycache__", ".pytest_cache", ".venv", "node_modules")
    shutil.copytree(source, target, ignore=ignored, symlinks=True)


def run_task(task: BenchmarkTask) -> BenchmarkResult:
    """Execute a ready task in disposable local copies and prove source non-mutation."""
    task.validate()
    if task.status != "ready":
        raise ValueError(f"Task {task.id!r} is a candidate, not an executable benchmark.")
    buggy_source, gold_source = Path(task.buggy_path or ""), Path(task.gold_path or "")
    if not buggy_source.is_dir() or not gold_source.is_dir():
        raise ValueError("Ready task checkout paths must exist locally; this runner never clones repositories.")
    before_buggy, before_gold = _tree_digest(buggy_source), _tree_digest(gold_source)
    started = __import__("time").monotonic()
    with tempfile.TemporaryDirectory(prefix="reprove-benchmark-") as temporary:
        root = Path(temporary)
        buggy_copy, gold_copy = root / "buggy", root / "gold"
        _copy_read_only(buggy_source, buggy_copy)
        _copy_read_only(gold_source, gold_copy)
        buggy_attempts = [Runner(buggy_copy).run(task.command) for _ in range(task.repetitions)]
        reproduced = all(not attempt.passed for attempt in buggy_attempts)
        gold_attempt = Runner(gold_copy).run(task.command) if reproduced else None
    unchanged = before_buggy == _tree_digest(buggy_source) and before_gold == _tree_digest(gold_source)
    exit_codes = [attempt.returncode for attempt in buggy_attempts]
    return BenchmarkResult(
        task_id=task.id,
        verdict="VALID" if reproduced and gold_attempt and gold_attempt.passed and unchanged else "INVALID",
        reproduced=reproduced,
        valid_under_gold_patch=bool(gold_attempt and gold_attempt.passed),
        deterministic=len(set(exit_codes)) == 1,
        source_unchanged=unchanged,
        duration_ms=int((__import__("time").monotonic() - started) * 1000),
        repetitions=task.repetitions,
        buggy_exit_codes=exit_codes,
        gold_exit_code=gold_attempt.returncode if gold_attempt else None,
    )


def write_results(results: list[BenchmarkResult], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(asdict(result), sort_keys=True) for result in results) + ("\n" if results else ""))


def read_results(path: Path) -> list[BenchmarkResult]:
    return [BenchmarkResult(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def report(results: list[BenchmarkResult]) -> dict[str, Any]:
    total = len(results)
    valid = sum(item.verdict == "VALID" for item in results)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only": True,
        "guarantee": READ_ONLY_GUARANTEE,
        "tasks": total,
        "valid_tasks": valid,
        "validity_rate": round(100 * valid / total, 1) if total else None,
        "reproduce_rate": round(100 * sum(item.reproduced for item in results) / total, 1) if total else None,
        "determinism_rate": round(100 * sum(item.deterministic for item in results) / total, 1) if total else None,
        "median_duration_ms": int(statistics.median(item.duration_ms for item in results)) if results else None,
        "results": [asdict(item) for item in results],
    }


def write_report(results: list[BenchmarkResult], output: Path) -> None:
    payload = report(results)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    markdown = output.with_suffix(".md")
    if not results:
        markdown.write_text("# Reprove benchmark report\n\n_No benchmark results yet. Candidate issues are intake metadata, not performance claims._\n")
        return
    markdown.write_text(
        "# Reprove benchmark report\n\n"
        f"**Read-only guarantee:** {READ_ONLY_GUARANTEE}\n\n"
        f"{payload['valid_tasks']}/{payload['tasks']} tasks valid · {payload['determinism_rate']}% deterministic · median {payload['median_duration_ms']} ms\n\n"
        "| Task | Verdict | Reproduced | Gold patch passes | Source unchanged |\n|---|---|---:|---:|---:|\n" +
        "\n".join(f"| {item.task_id} | {item.verdict} | {item.reproduced} | {item.valid_under_gold_patch} | {item.source_unchanged} |" for item in results) + "\n"
    )
