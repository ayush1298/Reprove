# Reprove — Devpost submission copy

## Inspiration

AI coding agents can write a plausible fix before anyone has shown the bug is real. That makes review a trust problem. We built Reprove to make execution—not model confidence—the basis for maintenance work.

## What it does

Reprove turns a claim into a native test that must fail deterministically on the current main branch before any fix loop can proceed. The fix loop is physically blocked from changing test files. A proposed fix then has to pass the same test, survive micro-mutations in the changed production region, and avoid regressions in neighboring tests. Every outcome is an evidence bundle, including honest refusals such as `CANNOT_REPRODUCE`, `NEEDS_INFO`, and `ENV_UNSUPPORTED`.

The upgrade verifier adds behavior canaries: it pins a dependency's old observed behavior, upgrades in an isolated run, and shows silent incompatibilities that a successful build would miss.

## What makes it different

We are not claiming to be a better coding agent, a universal migration engine, or the inventor of reproduction-test generation. Reprove is the verification layer around any of those tools. Its distinctive product surface is enforced proof-before-patch, immutable evidence tests, mutation-validated reproducers, and tracker-ready execution verdicts. A refusal is a useful result, not a failed demo.

## How we built it

The project is a dependency-light Python application with a local-first CLI, GitHub workflow scaffold, OpenAI Responses proposal adapter, Docker sandbox command construction, native Python/Node bootstrap detection, an evidence-bundle format, evaluation harness, and a no-build static control-room dashboard. It was built with Codex as part of OpenAI Build Week.

## Security and scope

Deployment execution uses Docker with no network, read-only source mounts, dropped capabilities, no-new-privileges, memory/CPU caps, and no mounted secrets. Repo text is treated as untrusted data in the model prompt. The current supported tier is conventionally configured Python and Node repositories; unsupported environments receive `ENV_UNSUPPORTED`, never a false `CANNOT_REPRODUCE`.

## What is next

The common kernel is designed for CVE upgrades, flaky-test repair, independent AI-PR audits, and regression-sentinel jobs. The immediate next production steps are GitHub App authentication, a managed isolated-runner fleet, and a published SWE-bench evaluation report.
