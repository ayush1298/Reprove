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
- GitHub event scaffold, OpenAI structured-proposal adapter, Docker hardened execution command, seeded demos, evaluation harness, and hackathon dashboard.

## Run it

Requires Python 3.11+ and pytest for the demos.

```bash
python -m pip install -e '.[dev]'
python -m pytest -p no:rerunfailures
python -m reprove.cli inspect .
```

Run the full demonstrated flows in [docs/DEMO.md](docs/DEMO.md). To view the control room, open [dashboard/index.html](dashboard/index.html) in a browser.
The six-slide hackathon pitch is available at [reprove-hackathon-deck.pptx](outputs/reprove-hackathon-deck.pptx).
For a ready-to-submit fallback walkthrough, use the narrated [reprove-demo.mp4](outputs/reprove-demo.mp4) (2:16).

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

The model integration only produces a typed proposal; it cannot override any execution gate. See [docs/DEVPOST.md](docs/DEVPOST.md) for positioning and [docs/EVALUATION.md](docs/EVALUATION.md) for honest benchmark methodology.

## Security posture

The deployment Docker command uses `--network none`, a read-only source mount, capability drop, no-new-privileges, and resource caps. The local runner scrubs common secret variables and disables machine-global pytest plugins. Never mount production credentials into a repository execution sandbox.

## Known limits

This hackathon release supports conventional Python and Node test layouts. It does not promise to build every repository, automate browser/UI bugs, or run an unbounded test suite. Those limits produce explicit evidence states rather than plausible success claims.
