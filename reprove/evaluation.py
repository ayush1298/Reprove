"""Gold-patch benchmark scoring with repeatable JSONL input, not opaque leaderboard claims."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .execution import Runner


@dataclass(slots=True)
class EvaluationResult:
    task: str
    reproduced: bool
    valid_under_gold_patch: bool
    deterministic: bool
    duration_ms: int


def score_task(task: str, buggy_root: Path, gold_root: Path, test_command: list[str], runs: int = 3) -> EvaluationResult:
    buggy = Runner(buggy_root)
    started = __import__("time").monotonic()
    outcomes = [buggy.run(test_command).passed for _ in range(runs)]
    reproduced = not any(outcomes)
    gold = Runner(gold_root).run(test_command).passed if reproduced else False
    return EvaluationResult(task, reproduced, gold, len(set(outcomes)) == 1, int((__import__("time").monotonic() - started) * 1000))


def summarize(results: list[EvaluationResult]) -> dict[str, float | int]:
    total = len(results) or 1
    reproduced = [item for item in results if item.reproduced]
    return {
        "tasks": len(results),
        "reproduce_rate": round(100 * len(reproduced) / total, 1),
        "validity_rate": round(100 * sum(item.valid_under_gold_patch for item in reproduced) / (len(reproduced) or 1), 1),
        "determinism": round(100 * sum(item.deterministic for item in results) / total, 1),
        "median_latency_ms": sorted([item.duration_ms for item in results])[len(results) // 2] if results else 0,
    }


def write_results(results: list[EvaluationResult], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(asdict(result)) for result in results) + "\n")
