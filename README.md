# Reprove

> **No fix without a failing test.**

Reprove is a verification-first maintenance agent. It turns bug reports and risky dependency upgrades into executable evidence, then refuses to fix anything it cannot prove is broken. It is deliberately a trust layer for coding agents—not a competing code generator.

Open [`dashboard/index.html`](dashboard/index.html) for the polished evidence control-room view.

## What is implemented

- Python + Node supported-tier bootstrap detection: CI workflow commands first, then devcontainer detection, then safe conventions; unsupported environments yield `ENV_UNSUPPORTED`.
- First-class execution verdicts: `REPRODUCED`, `CANNOT_REPRODUCE`, `NEEDS_INFO`, `ENV_UNSUPPORTED`, `NOT_A_BUG`, `FIX_VERIFIED`, and `FIX_REJECTED`.
- Deterministic fail-on-main and pass-after-fix gates (five runs by default).
- Source-only fix loop boundary, protected paths, assertion/skip linter, and micro-mutation validation of the changed production region.
- Neighboring-test blast-radius gate and objective, gate-derived confidence score.
- Issue-prover artifacts: JSON evidence bundle, Markdown issue comment, and draft-PR body. GitHub REST adapter is branch-scoped to `reprove/*`.
- Upgrade verifier with old-behavior canaries for silent breaking changes.
- FastAPI control plane with durable organizations, repositories, runs, live events, redacted 30-day artifacts, SHA-256 evidence manifests, and a responsive evidence cockpit.
- GitHub App JWT-to-installation-token authentication, webhook normalization/deduplication with review-only issue routing, AI-PR audit core, and hosted/self-hosted/managed isolated-runner contracts.
- Docker-hardened execution command, measured public issue-replay pilot, evaluation harness, CI, and hackathon dashboard.

## Installation and local use

### Requirements

- Python **3.11+** and `pip`
- Git, for inspecting repositories and running the public replay locally
- Docker Desktop or Docker Engine only for the optional multi-service control plane and hardened runner workflow

Reprove has been exercised on macOS and Linux. Windows users should run it in
**WSL2**; the production isolation contract relies on Linux Docker features
(read-only mounts, dropped capabilities, and network isolation). The local
CLI, API, dashboard, and unit suite do not require Docker.

### Install

```bash
git clone <your-fork-or-repository-url>
cd Reprove
python -m pip install -e '.[dev]'
```

### Verify the installation

```bash
python -m pytest -p no:rerunfailures
python -m reprove.cli inspect .
```

The first command runs the repository's safety, API, integration, runner, and
evaluation tests. The second reports whether the current checkout has a
supported Python or Node test configuration.

### Run the live evidence cockpit

```bash
reprove-api
# open http://127.0.0.1:8000
```

The cockpit persists organizations, repositories, runs, events, and redacted
evidence artifacts in SQLite locally, while using the same SQL schema as the
PostgreSQL deployment. To exercise the complete local flow, open **Start
evidence run**, keep the seeded checkout values, and queue the run; the Runs
and Proof vault views will show its gates and immutable bundle. See
[operations](docs/OPERATIONS.md) for Docker, GitHub webhooks, managed runners,
and retention guidance.

### Optional container control plane

```bash
docker compose up --build
```

This starts FastAPI, PostgreSQL, Redis, and the queue worker for local
evaluation. It is not required for the normal developer demo.

### Control-plane API

`/docs` exposes the live OpenAPI surface. The main operational endpoints are:

- `POST /v1/runs/issue-prover` and `POST /v1/runs/upgrade-verifier`;
- `GET /v1/runs/{id}` plus `GET /v1/runs/{id}/events` for SSE trace streaming;
- `GET /v1/runs/{id}/bundle` for immutable, redacted evidence JSON;
- `POST /v1/audits/pull-request` for independent AI-PR evidence checks;
- `POST /v1/github/webhooks` for signed GitHub delivery intake, plus `GET /v1/github/app/status` for safe configuration visibility;
- `POST /v1/runners`, `/v1/runners/{id}/leases`, and `/v1/runners/{id}/runs/{run_id}/complete` for capability-matched managed execution;
- `GET /v1/evaluations/swe-bench` for the published, intentionally unscored SWE-bench readiness report.
- `GET /v1/evaluations/public-issue-replay` for the measured public upstream pilot, always including its sample size.

The control room is served by `reprove-api` at `http://127.0.0.1:8000`.

### Measured evaluation proof

The first public upstream issue-replay pilot validates `pytest-dev/pytest#11706` against its accepted fix: **3/3 deterministic failures on the pinned buggy revision, then a pass on the accepted fix**. That is **100% reproduce rate, gold validity, determinism, and tracked-source integrity at N=1**—a small, honest pilot, not a generalized model-performance claim. See the [measured report](reports/public-issue-replay-pilot.json), [exact regression scenario](benchmarks/replay/pytest_11706_regression.py), and [evaluation protocol](docs/EVALUATION.md).

## Architecture

```text
issue / upgrade claim
        │
        ▼
 bootstrap → native evidence test → fail 5/5 on main
        │                             │
        │                         refusal verdicts
        ▼
 source-only fix boundary → pass 5/5 → mutation → blast radius
        │
        ▼
 evidence bundle + issue comment + draft PR body
```

The model integration only produces a typed proposal; it cannot override any execution gate. See [docs/EVALUATION.md](docs/EVALUATION.md) for the honest benchmark methodology.

## Built with Codex and GPT-5.6

OpenAI Codex, using GPT-5.6, was used as a development collaborator for this
hackathon project: planning the evidence-first product flow, implementing and
refining the FastAPI/API and dashboard experience, expanding test coverage,
and improving the developer documentation and evaluation presentation.

That assistance is deliberately separated from the product's trust boundary:
Reprove does **not** claim that Codex or GPT-5.6 autonomously proves a fix, and
the shipped local workflow has no required OpenAI API key or runtime model
dependency. Any model/provider proposal is treated as untrusted input until it
passes the deterministic execution, immutability, mutation, and blast-radius
gates.

## Security posture

The deployment Docker command uses `--network none`, a read-only source mount, capability drop, no-new-privileges, and resource caps. The local runner scrubs common secret variables and disables machine-global pytest plugins. Never mount production credentials into a repository execution sandbox.

## Known limits

This hackathon release supports conventional Python and Node test layouts. It does not promise to build every repository, automate browser/UI bugs, or run an unbounded test suite. Those limits produce explicit evidence states rather than plausible success claims.
