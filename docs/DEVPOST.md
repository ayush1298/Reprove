# Reprove — Devpost submission copy

## Inspiration

AI coding agents can produce a plausible patch before anyone has proved the reported problem is real. That leaves maintainers reviewing model confidence, not engineering evidence. Reprove was built to reverse that order: prove the claim first, then allow a fix to be considered.

## What it does

Reprove turns an issue or risky dependency upgrade into executable evidence. An evidence test must fail deterministically on the pinned baseline before a repair workflow can proceed. The repair boundary rejects test-file edits and assertion weakening; a proposed source change must then pass the same evidence, survive micro-mutations, and avoid nearby regressions.

Every outcome is useful and explicit: `REPRODUCED`, `CANNOT_REPRODUCE`, `NEEDS_INFO`, `ENV_UNSUPPORTED`, `NOT_A_BUG`, `FIX_VERIFIED`, or `FIX_REJECTED`. The result is a redacted, replayable evidence bundle rather than an opaque “AI says it works.”

Reprove also verifies dependency upgrades with behavior canaries. It pins an application's old observed behavior, checks the upgraded dependency in isolation, and exposes silent breaking changes that a green build can miss.

## What makes it different

Reprove is not another code generator or a universal migration engine. It is the verification layer around coding agents and maintenance workflows.

- Proof before patch is enforced by execution, not a prompt.
- Evidence tests and protected paths are immutable during repair.
- Micro-mutation and nearby-test gates reject vacuous or overly narrow evidence.
- Refusals are first-class outputs rather than hidden failures.
- GitHub issue intake, AI-PR audit, upgrade canaries, and incident intake all produce the same durable evidence model.

## How we built it

Reprove is a Python/FastAPI control plane with a local-first CLI, durable run/event/artifact ledger, static evidence cockpit, Python/Node bootstrap detection, and hardened execution contracts. GitHub App authentication signs a short-lived JWT and exchanges it for ephemeral installation tokens; webhook triggers are captured as review-only intakes. Managed runners must match read-only-source and network-isolation capabilities, and only the runner holding a lease can complete its evidence bundle.

The dashboard is deliberately focused on Mission control, Runs, Proof vault, Evaluation, and Connections. It exposes evidence, GitHub App readiness, runner capacity, and evaluation provenance without auto-publishing anything upstream.

## Accomplishments that we're proud of

We ran a real public upstream issue-replay pilot, not just a synthetic demo. For [pytest #11706](https://github.com/pytest-dev/pytest/issues/11706), the accepted upstream regression scenario failed **3/3** on the pinned buggy revision and passed on the accepted upstream fix ([PR #12279](https://github.com/pytest-dev/pytest/pull/12279)). The report shows:

- **100% reproduce rate**
- **100% gold-patch validity**
- **100% determinism**
- **100% tracked-source integrity**
- **N=1**, displayed beside every rate

This is intentionally a proof of the evidence contract, not a generalized claim about autonomous test generation. The exact revisions, regression scenario, result hashes, and limitations are published in `reports/public-issue-replay-pilot.json`.

## Challenges we ran into

An official SWE-bench run is Docker-based and resource-intensive. This ARM development machine did not have a running Docker daemon and had 45 GB free, below the evaluator's recommended capacity. Instead of inventing a SWE-bench score, we published the evaluator readiness protocol and ran the smaller, pinned public issue replay above. The dashboard distinguishes the measured pilot from the unscored SWE-bench follow-on.

## What we learned

Evaluation quality is product quality for an evidence tool. A percentage without a task count, pinned revisions, a gold control, and source-integrity checks is not proof. Treating invalid or environment-confounded runs as explicit outcomes made the project more credible and made the demo easier to explain.

## What's next

Run a preregistered multi-project corpus on the official SWE-bench Docker evaluator, publish raw predictions and evaluator output, then report resolution, validity, determinism, mutation survival, cost, and latency separately. Expand the same kernel to CVE upgrades, flaky-test repair, independent AI-PR audits, and regression-sentinel jobs.
