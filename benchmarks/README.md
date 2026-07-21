# Benchmark intake

`candidates.jsonl` is a catalog of public, manually-reviewed issue metadata. It is deliberately **not** an execution queue.

Reprove never clones a candidate, opens a branch, files or comments on an issue, creates a pull request, or uses a GitHub token while benchmarking. To promote a candidate, a maintainer must independently provide two local, pinned, license-compatible worktrees and complete the `ready` fields: `source_commit`, `gold_commit`, `buggy_path`, `gold_path`, and `command`.

```bash
reprove benchmark validate benchmarks/candidates.jsonl
reprove benchmark run benchmarks/ready.jsonl --output artifacts/evaluation/results.jsonl
reprove benchmark report artifacts/evaluation/results.jsonl
```

The run command copies those local worktrees into a temporary directory and records that the supplied sources' content digests are unchanged. Results without a valid gold-patch pass are invalid, not successes.

## SWE-bench pilot

[`swebench-shortlist.json`](swebench-shortlist.json) is a separate intake manifest for the official SWE-bench evaluator. It does not pretend its shortlist has been executed. The paired [`../reports/swe-bench-pilot.json`](../reports/swe-bench-pilot.json) reports the exact execution state, quarantine list, and command required for the first scored task. This makes the dashboard useful before expensive container evaluation begins while preventing a candidate count from being mistaken for an accuracy score.

## Intake bar

Use a task only when it has a public issue with a minimal reproduction or clear expected behavior, a linked accepted fix, a permissive/compatible license, a pinned pre-fix commit, a deterministic command, and no production credentials/network service dependency. Exclude security disclosures, live customer data, external API dependence, and tasks that need secrets.
