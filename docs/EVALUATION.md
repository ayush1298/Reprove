# Evaluation protocol

Reprove does not publish invented benchmark numbers. Its evaluator separates **candidate intake** from execution and makes the safe path the default.

## Read-only by construction

Benchmark tooling has no GitHub client or publishing path. It does not clone candidates, authenticate to GitHub, create branches, commit, open pull requests, post comments, or update issues. An executable task only points to two caller-provided local, pinned worktrees. Reprove copies both into a temporary directory, runs there, and verifies the original source digests are unchanged.

The initial public candidates are in [`benchmarks/candidates.jsonl`](../benchmarks/candidates.jsonl); they are research metadata, not results or permission to modify another project.

## Reproducible scoring

Promote a reviewed candidate to `ready` only after adding the pre-fix commit, accepted-fix commit, compatible license, two local worktree paths, and a narrow deterministic command. Then run:

```bash
reprove benchmark validate benchmarks/ready.jsonl
reprove benchmark run benchmarks/ready.jsonl --output artifacts/evaluation/results.jsonl
reprove benchmark report artifacts/evaluation/results.jsonl --output artifacts/evaluation/report.json
```

Every task runs its command three times against the buggy worktree and once against the gold worktree. A valid result requires all buggy attempts to fail, the gold worktree to pass, deterministic buggy exit codes, and unchanged source digests. The report records invalid tasks plainly; it must never turn environmental failure into a success.

## What to publish

Publish task ids, repository/issue links, pinned commits, exact commands, environment/image digest, raw JSONL, report, task exclusions, wall time, and any agent/model cost. Report validity, reproducibility, determinism, mutation-kill rate, false-positive rate, latency distribution, and cost separately—never as one opaque score. The project test suite already covers adversarial evidence gates (test edits, assertion weakening, vacuous evidence, and upgrade canaries); benchmark claims begin only after a reviewed public result set exists.
