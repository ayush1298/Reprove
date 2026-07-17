# Evaluation protocol

Reprove does not publish invented benchmark numbers. This repository ships the repeatable evaluator and the metric definitions; execute it against licensed SWE-bench Lite/Verified worktrees before publishing a score.

## Gold-patch scoring

For each task, place two checked-out worktrees beside each other:

```
benchmarks/<task>/buggy/
benchmarks/<task>/gold/
```

Run the generated evidence test in `buggy/` three times, then in `gold/` once:

```python
from pathlib import Path
from reprove.evaluation import score_task, summarize, write_results

result = score_task("task-id", Path("benchmarks/task-id/buggy"), Path("benchmarks/task-id/gold"), ["python", "-m", "pytest", "tests/test_evidence.py"])
print(summarize([result]))
write_results([result], Path("artifacts/evaluation.jsonl"))
```

Run the collection three times and report mean ± spread for reproduce rate, validity rate, mutation survival, determinism, false positives, cost, and latency. The included `tests/` suite is the adversarial gate suite: test edits, assertion weakening, vacuous evidence, and an upgrade canary are all exercised locally.
