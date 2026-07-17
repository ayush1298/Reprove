import json
from pathlib import Path

import pytest

from reprove.benchmark import BenchmarkTask, load_manifest, run_task, write_report, write_results
from reprove.cli import main


def _task(tmp_path: Path) -> BenchmarkTask:
    buggy, gold = tmp_path / "buggy", tmp_path / "gold"
    buggy.mkdir(); gold.mkdir()
    (buggy / "check.py").write_text("raise SystemExit(1)\n")
    (gold / "check.py").write_text("raise SystemExit(0)\n")
    return BenchmarkTask(
        id="local-boundary", repository="https://github.com/example/project", issue_url="https://github.com/example/project/issues/1",
        title="Local boundary", source_commit="a" * 40, gold_commit="b" * 40, buggy_path=str(buggy), gold_path=str(gold),
        command=["python", "check.py"], status="ready", license="MIT",
    )


def test_ready_benchmark_uses_copies_and_preserves_sources(tmp_path):
    task = _task(tmp_path)
    before = (Path(task.buggy_path) / "check.py").read_text()
    result = run_task(task)
    assert result.verdict == "VALID"
    assert result.reproduced and result.valid_under_gold_patch and result.deterministic
    assert result.source_unchanged and result.read_only
    assert (Path(task.buggy_path) / "check.py").read_text() == before


def test_candidate_cannot_execute_and_manifest_validation_is_read_only(tmp_path, capsys):
    candidate = {
        "id": "intake-only", "repository": "https://github.com/example/project", "issue_url": "https://github.com/example/project/issues/9",
        "title": "A candidate", "status": "candidate",
    }
    manifest = tmp_path / "tasks.jsonl"; manifest.write_text(json.dumps(candidate) + "\n")
    assert main(["benchmark", "validate", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["read_only"] is True
    with pytest.raises(ValueError, match="candidate"):
        run_task(load_manifest(manifest)[0])


def test_report_declares_empty_results_not_a_score(tmp_path):
    results = tmp_path / "results.jsonl"; write_results([], results)
    report = tmp_path / "report.json"; write_report([], report)
    assert json.loads(report.read_text())["tasks"] == 0
    assert "No benchmark results yet" in report.with_suffix(".md").read_text()
