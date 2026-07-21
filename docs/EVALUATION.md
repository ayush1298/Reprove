# Evaluation protocol

Reprove does not publish invented benchmark numbers. Its evaluator separates **candidate intake** from execution and makes the safe path the default.

## Read-only by construction

Benchmark tooling has no GitHub client or publishing path. It does not clone candidates, authenticate to GitHub, create branches, commit, open pull requests, post comments, or update issues. An executable task only points to two caller-provided local, pinned worktrees. Reprove copies both into a temporary directory, runs there, and verifies the original source digests are unchanged.

The initial public candidates are in [`benchmarks/candidates.jsonl`](../benchmarks/candidates.jsonl); they are research metadata, not results or permission to modify another project.

## Published SWE-bench readiness report

[`reports/swe-bench-pilot.json`](../reports/swe-bench-pilot.json) is the project’s first public evaluation artifact. It intentionally reports **NOT_RUN** and a null resolution rate: this is an honest, reproducible intake report—not a leaderboard claim. It records three initial SWE-bench tasks, one test-integrity control, and five task ids quarantined because SWE-bench maintainers documented prior gold-patch failures.

The first scored run uses the official evaluator with `sympy__sympy-20590`, pinned image digests, immutable source/test digests, network disabled after image provisioning, and checked-in predictions/evaluator JSON. The official [SWE-bench repository](https://github.com/SWE-bench/SWE-bench) documents the evaluator and task format; its [known-invalid-instance notice](https://github.com/SWE-bench/SWE-bench/issues/267) informs the quarantine list. The [test-manipulation report](https://github.com/SWE-bench/SWE-bench/issues/538) is why Reprove includes an explicit integrity-control task.

## Measured public issue-replay pilot

[`reports/public-issue-replay-pilot.json`](../reports/public-issue-replay-pilot.json) records a real execution against [pytest issue #11706](https://github.com/pytest-dev/pytest/issues/11706) and its accepted reintroduced fix [PR #12279](https://github.com/pytest-dev/pytest/pull/12279). The externalized upstream regression scenario failed **3/3** on the pinned buggy revision and passed on the accepted fixed revision: **100% reproduce rate, 100% gold validity, 100% determinism, and 100% tracked-source integrity (N=1)**.

This is deliberately framed as an N=1 proof of the execution/evidence contract—not a claim about autonomous test generation or a generalized repair rate. The exact regression test lives in [`benchmarks/replay/pytest_11706_regression.py`](../benchmarks/replay/pytest_11706_regression.py), outside both upstream worktrees. The raw-log hashes, revisions, runtime, and command outcome are recorded in the report.

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
