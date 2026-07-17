# Reprove — Verification-First Code Maintenance

> **Tagline:** *No fix without a failing test.*
>
> **One-liner:** Everyone is building agents that write code. Reprove is the agent that **proves** code — it converts vague bug reports and risky dependency upgrades into executable evidence (failing tests), and refuses to fix anything it cannot first prove is broken.

**Hackathon:** OpenAI Build Week (Devpost), deadline Jul 21, 2026 · **Track:** Developer Tools
**Stack:** GPT-5.6 (reasoning/agent loops), Codex (to build the project itself — document this, it's the event theme), Docker sandbox, GitHub App/API, Python + Node target ecosystems.

---

## 1. Positioning: how we answer "isn't this already done?"

This is the question judges (and later, users) will ask, so we answer it head-on instead of hoping it doesn't come up.

**The honest concession first.** Fragments of what we do exist: research papers generate bug-reproduction tests, a solo-dev CLI (`rp`) formalizes repro-then-fix locally, Metabase built an internal repro bot for their own codebase, and the dependency-migration space has serious incumbents (AWS Transform, Moderne, Codemod, Infield, fossabot). We do not claim to have invented reproduction, migration, or test generation.

**The actual claim.** No shipped, general-purpose product provides an **execution-verified evidence layer** for code maintenance — one that (a) is autonomous and tracker-native, (b) enforces hard verification gates *in code, not in prompts*, and (c) treats "refuse to proceed" as a first-class output. Every incumbent's success metric is *changes shipped*. Ours is *claims proven*. That is a category difference, not a feature difference — and it's why incumbents structurally won't copy it: a tool judged on PRs merged cannot easily adopt a design whose flagship behavior is refusing to open a PR.

**Three-part defense (memorize this for Q&A):**
1. **Demand is proven, supply is absent.** Metabase engineers built a bespoke internal repro-bot because nothing existed to buy. The Hono community filed a feature request asking for exactly this workflow. Google published research on reproduction-test cogeneration. Multiple independent parties want it; nobody sells it.
2. **Fragments ≠ product.** `rp` = a manual, local, single-issue CLI with shell-script reproducers. Repro-Bot = hand-crafted recipes for one codebase. Research systems = benchmarks, not GitHub Apps. Assembling fragments into a reliable, autonomous, multi-tenant product with hard gates *is the work* — the same way Dropbox "just" productized rsync.
3. **Our unique surface is the gates, not the loop.** Anti-cheat test immutability, mutation-validated tests, canary tests for silent upgrade breakage, and evidence-bundle PRs exist in **no** product on the market (see §4 matrix). These aren't polish; they're the product.

**The pitch sentence:** *"Copilot answers 'can AI fix this?' Reprove answers 'how do we know it's actually fixed?' — and as AI writes more of the world's code, the second question is the one that scales."*

---

## 2. What we are explicitly NOT claiming (anti-"duplicated work" guardrails)

Write these into the Devpost submission verbatim-ish. Pre-empting overlap accusations reads as maturity; getting caught overclaiming reads as naivety.

- We are **not** a better coding agent than Copilot/Codex/Devin. We are the verification layer that makes any of them trustworthy (and auditable).
- We are **not** a migration engine competing with AWS Transform or Moderne on transformation breadth. Our migration module contributes one thing they lack: **proof of behavior preservation** via generated canary tests.
- We are **not** inventing bug-reproduction-test generation (active research field). We are productizing it with reliability gates none of the research systems or internal tools ship.
- We are **not** claiming to build/run arbitrary repos universally (nobody can). We declare a supported tier honestly and degrade gracefully outside it.

---

## 3. Architecture: one kernel, pluggable modules

### 3.1 The kernel (built during hackathon)

| Layer | Name | What it does |
|---|---|---|
| L1 | **Execution substrate** | Docker sandbox; clones repo; detects toolchain; uniform `build()` / `test(selector)` / `run(cmd)` interface. Bootstrap strategy, in priority order: ① parse the repo's own GitHub Actions workflow (the maintainers' install/test commands are literally written there — replay them), ② `devcontainer.json` if present, ③ convention defaults (Python: pip/uv + pytest; Node: npm/pnpm + jest/vitest), ④ give up with an honest `ENV_UNSUPPORTED` verdict. No outbound network during test execution; read-only GitHub token + branch-create on `reprove/*` only; repo code is treated as untrusted input (prompt-injection aware). |
| L2 | **Evidence engine** | Given a claim ("this issue is a bug", "this upgrade changes behavior"), produce executable proof: tests written in the repo's own test framework that fail deterministically on current main. Owns all verification gates (§5). |
| L3 | **Fix loop** | GPT-5.6 iterate-until-green: propose diff → run evidence tests + neighboring regression tests → read failures → revise. **Hard rule enforced in code: the fix loop cannot write to test files.** |
| L4 | **Evidence bundle + reporting** | Every output is a PR/comment containing: the failing test, logs of it failing on main, the fix diff, logs of it passing after, regression results, mutation-check results, determinism runs, a confidence score from objective signals, and a plain-English root-cause narrative. |

### 3.2 Module A — Issue Prover (hackathon: full build)

**Trigger:** label `reprove` on a GitHub issue, comment `@reprove reproduce this`, or webhook on new issues (opt-in).

**Pipeline:**
1. **Parse** the issue → extract claimed behavior, environment hints, repro steps; pull linked code/tracebacks.
2. **Localize** — agent explores the codebase (grep, read files, run existing related tests) to find the implicated region.
3. **Generate multi-facet reproduction tests** (2–3): one for the literally reported scenario, 1–2 for inferred boundary cases. (Research shows single tests overfit to the reported symptom and admit partial fixes.)
4. **Gate 1 — fail-on-main:** each test must fail on current main, deterministically (5 consecutive runs). Tests that pass are discarded; if all pass → verdict `CANNOT_REPRODUCE` with full attempt log.
5. **Publish evidence:** push branch `reprove/issue-<n>` with the failing test; comment on the issue with the verdict + logs.
6. **(Optional stage) Fix loop** → Gate 2 (test passes) → anti-cheat check → mutation check → regression blast-radius check → open evidence-bundle PR.

**Verdict enum (first-class outputs, all valuable):**
- `REPRODUCED` — failing test committed, evidence posted.
- `CANNOT_REPRODUCE` — with the log of every attempt (lets maintainers close stale issues confidently).
- `NEEDS_INFO` — agent posts *targeted* questions to the reporter ("which Python version? does it occur with X disabled?").
- `ENV_UNSUPPORTED` — bootstrap failed; never conflated with cannot-reproduce (trust-critical distinction).
- `NOT_A_BUG` — reproduction shows behavior matches documented intent.

### 3.3 Module B — Upgrade Verifier (hackathon: happy path only)

Deliberately **demoted from co-headline to supporting module** — migration execution is a crowded field. Our contribution is verification:

1. Bump dependency in sandbox → run build/tests → capture breakage as evidence (if any).
2. Fetch changelog/migration guide → map documented breaking changes to actual usage sites.
3. **Canary generation (the novel part):** for behavior-level changes that would NOT break the build — changed defaults, subtle return-value changes — generate *canary tests* that pin the application's observed dependence on the OLD behavior, then run them under the NEW version and report which canaries flip. This converts "silent breaking change" (the #1 reason teams fear upgrades) into a visible red test. **No migration product on the market does this.**
4. Apply migrations via fix loop → iterate to green → evidence-bundle PR listing: what broke, what was changed, which canaries flipped, which behaviors are proven preserved.

### 3.4 Modules C–F — roadmap (slide only, do not build)

- **C. CVE fast path:** advisory-triggered Module B with a "minimum viable upgrade" planner (smallest jump clearing the CVE). The enterprise wedge.
- **D. Flaky-test handler:** run suspect test N times, diff divergent runs, hypothesize nondeterminism source, fix; evidence = "7/50 failures before → 0/200 after." (Trunk/BuildPulse/Datadog detect & quarantine; none fix.)
- **E. AI-PR Auditor (strategic sleeper):** for incoming agent-written PRs, independently reproduce the linked issue, verify the PR against *our* evidence, reject PRs that weaken/delete tests. Positions us as complementary to Copilot/Codex, not competing. As agent-written code volume explodes, "who reviews the robot" is the growth market.
- **F. Regression sentinel:** mine merged bug-fix PRs that shipped without tests; retroactively generate the missing regression test from the fix diff + original issue.

---

## 4. Competitive landscape: every existing solution, and exactly what we do differently

### 4.1 Bug-reproduction / issue-resolution side

| Existing solution | What it actually is | What we do differently |
|---|---|---|
| **GitHub Copilot coding agent** (GA, mainstream) | Assign an issue → it plans, writes code, runs tests, opens a PR. Goes **straight from issue to fix**. Documented weakness: ambiguous issues produce best-guess PRs that "technically address the issue as written but miss intent." Can edit tests to get green. | We invert the flow: **proof before patch**. We refuse to fix unpinned bugs, physically block test edits during fixing, and can audit Copilot's own PRs (Module E). Complementary gate, not competing generator. |
| **`rp` (Pekka Enberg, OSS CLI, Mar 2026)** | Local 3-command workflow (inspect/check/fix); reproducer = standalone **shell script** in a `.rp/` dir; delegates to Claude Code/Codex; one issue at a time; GitHub/Linear integration listed as future work. | Autonomous **service** (triages the backlog unprompted, replies on the tracker) vs. manual CLI. Repro artifact = **native-framework test that merges into the suite** as permanent regression protection vs. throwaway script. Adds gates rp lacks: determinism screening, anti-cheat, mutation validation, multi-facet tests. Platform (upgrades/flakes/audit) vs. single pipeline. |
| **Metabase Repro-Bot** (internal tool, open-sourced as template, Apr 2026) | Reproduces issues for the Metabase codebase; writes a failing test on success; posts to Linear. Built on hand-written, Metabase-specific environment recipes and domain "folklore." | **General-purpose and self-configuring** (CI-config replay + devcontainer + convention tiers) vs. one hand-tuned codebase. Their existence is our best demand evidence: engineers built this internally because nothing existed to buy. |
| **GitHub AI issue intake action** | Analyzes issue **text**, suggests labels / "needs more info." | We **execute**. Our verdicts are backed by sandbox runs, not text vibes: a `CANNOT_REPRODUCE` comes with the log of actual attempts. |
| **Academic BRT research** (Google patch/test cogeneration; SWE-Doctor; validator agents) | Papers + benchmarks demonstrating reproduction-test generation works and that single tests overfit. | We productize with reliability gates none of them ship, on real trackers, with a published eval. Research validates the direction — cite it, don't compete with it. |
| **Ranger / Qodo / Tusk-style AI QA & test-gen** | Generate tests for coverage/new code; pattern-level PR risk flagging; bug classification/routing. | Their tests come from *code*; our tests come from *claims* (issues, upgrades) and must fail first. Nobody in this group does issue-grounded adversarial reproduction. |
| **Sentry AI / observability autofix** | Crash/trace-triggered suggestions in APM context. | Different input (runtime telemetry vs. tracker claims); no fail-first invariant; no tracker-native triage verdicts. Also a future intake source for us (§10). |

### 4.2 Dependency / migration side

| Existing solution | What it actually is | What we do differently |
|---|---|---|
| **Dependabot / Renovate** | Version-bump PRs; Renovate adds crowd-sourced Merge Confidence stats. | They tell you an update exists and how it went *for others*; we execute it against **your** code and prove behavior preservation with canaries. |
| **Infield** | Managed (substantially human-in-the-loop) upgrade service, Ruby/JS/Python; incremental upgrade plans; proprietary incompatibility database. | We're a self-serve product, not a service; and we generate **executable proof** (canaries), not advisory plans. |
| **FOSSA fossabot** | Breaking-change detection + static impact analysis layered on Dependabot PRs; JS/TS preview. | Analysis vs. **execution**: fossabot tells you what *might* break; we run the migration, fix it, and show which pinned behaviors actually changed. |
| **AWS Transform / Amazon Q** | Enterprise modernization agents (Java/Node/Python upgrades, .NET, mainframe); continuous-modernization scanning across repo fleets. | AWS-ecosystem, enterprise-scale, recipe/learning-based; verifies "build + existing tests pass." **Existing tests don't cover silent behavior changes — our canaries target exactly the uncovered surface.** We serve the long tail of ordinary repos, tracker-natively. |
| **Moderne / OpenRewrite** | Deterministic, auditable refactoring recipes at massive scale (Java-centric). | Recipe-based: covers what someone has encoded. We reason from changelogs for arbitrary libraries and **prove** outcomes with generated tests rather than relying on recipe correctness. |
| **Codemod.com** | Compiler-aware code-intelligence tooling for agents running large migrations. | Great execution infrastructure; no evidence layer. (Potential future integration, not a rival.) |

### 4.3 The differentiator list (what NO shipped product provides)

Use this list verbatim in the Devpost "what's novel" section. Honesty column included so we never overclaim.

| # | Core feature | Closest fragment elsewhere |
|---|---|---|
| 1 | **Refusal guarantee:** no fix proposed without a test that demonstrably failed on main first — enforced by execution | `rp` has the workflow but manual + script-based; research validators have it in benchmarks |
| 2 | **Anti-cheat enforcement:** fixing agent filesystem-blocked from editing test files; assertion-weakening diffs auto-rejected | Nobody. Copilot demonstrably edits tests to pass |
| 3 | **Mutation-validated repro tests:** generated test must catch micro-mutations of the fixed region or it's rejected as vacuous | Mutation testing exists (PIT/mutmut); using it as an automated gate on AI-generated repro tests does not |
| 4 | **Multi-facet reproduction** (reported case + inferred boundaries) to block partial fixes | Research only (SWE-Doctor) |
| 5 | **Canary tests for silent upgrade breakage** — pin old behavior, show which pins snap under new version | Nobody: AWS/Moderne/Codemod/Infield/fossabot all stop at "build + existing tests pass" |
| 6 | **Executed triage verdicts on the tracker** (`REPRODUCED` / `CANNOT_REPRODUCE`+attempt-log / `NEEDS_INFO`+targeted questions / `ENV_UNSUPPORTED` / `NOT_A_BUG`) | GitHub intake action = text-only; Repro-Bot = one codebase |
| 7 | **Evidence-bundle PR format** with confidence scored from objective signals (gates passed), not model vibes | Nobody as a format/standard |
| 8 | **AI-PR auditing:** independently reproduce the issue an agent PR claims to fix; verify against our evidence | Nobody |
| 9 | **One kernel across bugs / upgrades / flakes / audits** | Every competitor is single-purpose |
| 10 | **Published reproduce-rate benchmark** shipped with the product | Nobody publishes theirs |

---

## 5. Reliability gates (spec)

1. **Gate 1 — fail-on-main:** every evidence test must fail on current main, 5/5 consecutive runs (determinism screen). Flaky evidence is not evidence.
2. **Gate 2 — pass-after-fix:** verified by execution, never by model self-report.
3. **Anti-cheat:** fix-loop diffs touching test files are rejected pre-apply (path-based enforcement); a linter rejects diffs that delete/weaken assertions or add skip markers anywhere.
4. **Mutation check:** after Gate 2, inject 2–3 micro-mutations into the fixed region; the evidence test must fail on each; otherwise the test is vacuous → regenerate or downgrade.
5. **Blast radius:** run nearest-neighbor regression tests (full suite if fast); any new failure ⇒ PR ships as draft with warning, never clean.
6. **Verdict integrity:** environment failures are never reported as reproduction failures.
7. **Tiered autonomy (config per repo):** `evidence-only` → `draft-pr` (default) → `auto-pr` for low-risk classes (e.g., patch bumps).
8. **Sandbox security:** no network during test execution; secrets never mounted; least-privilege GitHub token; repo content treated as untrusted (prompt-injection-aware system design).
9. **Confidence score** = weighted objective signals: gates passed, facets agreeing, changelog explicitness, blast-radius cleanliness.

---

## 6. Evaluation plan (in detail — this is a first-class deliverable)

Almost no hackathon team ships an eval. Ours directly hits the "Technological Implementation" and "Potential Impact" judging criteria and is our best anti-vaporware proof.

### 6.1 Datasets
- **Offline benchmark:** 15–25 tasks from **SWE-bench Lite / Verified** (Python; prebuilt Docker images sidestep environment bootstrapping so we measure the *pipeline*, not our env luck).
- **Live-fire set:** 5–10 real open issues from 3–4 active OSS repos in our supported tier (pre-run privately; pick a spread of reproducible / non-reproducible / underspecified).
- **Adversarial gate suite:** hand-built unit tests of our own safety rails (below).

### 6.2 The gold-patch trick (automatic ground truth — explain this in the demo)
SWE-bench tasks ship with the **gold patch** (the real fix that resolved the issue). Therefore, for each task, a generated reproduction test can be scored with zero human labeling:
- must **FAIL** on the buggy commit (true reproduction), and
- must **PASS** after applying the gold patch (tests the right behavior, not an accident).

### 6.3 Metrics to report (README + Devpost + demo slide)
| Metric | Definition | How measured |
|---|---|---|
| **Reproduce rate** | % of tasks where ≥1 generated test fails on buggy commit | primary headline number |
| **Validity rate** | % of reproduced tasks whose test passes under gold patch | gold-patch trick |
| **Mutation survival** | % of evidence tests that catch injected micro-mutations | gate 4 run in eval mode |
| **Determinism** | % of tests with 5/5 consistent outcomes | gate 1 logs |
| **False-positive rate** | % of `REPRODUCED` verdicts that are wrong (test fails for env/flake reasons) | manual audit of the small set |
| **Fix rate (secondary)** | % of reproduced tasks fixed to green through all gates | de-emphasize; we're an evidence product |
| **Cost & latency** | median $ and minutes per issue | from run logs; judges always ask |

Run the whole benchmark **N=3** times and report mean ± spread — reporting variance signals engineering maturity.

### 6.4 Adversarial gate tests (prove the rails hold)
- Feed the fix loop a planted "fix" that edits the test file → assert rejection.
- Feed a fix that deletes an assertion → assert linter rejection.
- Feed a vacuous always-fails-then-always-passes test → assert mutation check catches it.
- Feed a time-dependent flaky test → assert determinism screen flags it.
- Feed an issue whose "bug" is documented behavior → assert `NOT_A_BUG` path.

### 6.5 What "good" looks like (set expectations pre-registered)
Reproduce rate 40–60% on SWE-bench-style tasks would be strong for a week's build (research systems with far more machinery land in this band); validity >85% among reproduced; zero adversarial-gate escapes. Publishing honest mid-range numbers with variance beats claiming 95% and being disbelieved.

---

## 7. Demo script (2–3 min video + live fallback)

**Setup:** pre-record everything; keep one live-clickable seeded demo repo as backup. Show raw terminal logs on screen — judges trust logs over dashboards.

| Time | On screen | What to SAY |
|---|---|---|
| 0:00–0:20 | Copilot PR for a vague issue, looks plausible | "Coding agents ship fixes for bugs nobody ever pinned down. Plausible ≠ proven. Reprove is the agent that proves." |
| 0:20–1:00 | Label a real OSS issue `reprove` → agent trace → **red pytest output on main** → evidence comment appears on the issue | "Vague report in — executable proof out. This test fails on main, five out of five runs. That comment is the triage every maintainer wishes they had time for." |
| 1:00–1:25 | Fix loop runs → same test goes **green** → evidence-bundle PR | "The fix is verified against evidence it was never allowed to touch." |
| 1:25–1:50 | **The refusal moment:** planted cheating fix that deletes an assertion → system auto-REJECTS with explanation | "Every other demo this week shows an agent succeeding. Here's ours refusing to cheat. This gate is enforced in code, not in a prompt." |
| 1:50–2:15 | Upgrade demo: version bump → canary test flips red on a *silent* behavior change existing tests missed | "No migration tool on the market catches this class of breakage. We pin the old behavior and show you exactly which pins snapped." |
| 2:15–2:35 | Eval slide: 4 headline metrics ± variance; adversarial gates 0 escapes | "We don't ask you to trust the demo — here's the benchmark, with gold-patch-verified ground truth." |
| 2:35–2:50 | Roadmap: modules C–F; 'Reproduced ✅ by Reprove' badge on OSS issues | "One kernel; bug triage today, upgrade proofs today, AI-PR auditing next — the trust layer for the age of AI-written code." |

**Also mention in the writeup:** demand evidence (Metabase built this internally; Hono community requested it), Codex-built development log (event theme), sandbox security posture, and the §2 "what we're NOT claiming" honesty section.

---

## 8. Six-day build plan

| Day | Deliverable |
|---|---|
| 1 | Kernel L1: sandbox, CI-config replay bootstrapper, Python+Node adapters, verdict enum. (Build with Codex; keep the session logs.) |
| 2 | Kernel L2: evidence engine + Gates 1/6 (fail-on-main, determinism, env-vs-repro verdict separation). |
| 3 | Module A end-to-end on GitHub: issue → branch with failing test → evidence comment. Fix loop + Gates 2/3 (anti-cheat). |
| 4 | Gates 4/5 (mutation, blast radius). Module B happy path on 2–3 libraries with known breaking majors + one canary demo. |
| 5 | Eval harness on SWE-bench subset (gold-patch scoring), adversarial gate suite, evidence-bundle PR formatting, minimal status page. |
| 6 | Demo video, Devpost writeup (positioning §1–§2, matrix §4, metrics §6), fallback demo repo, buffer. |

**Cut order if behind:** status page → Module B breadth → live-fire set. **Never cut:** the eval, the refusal demo, the anti-cheat gate.

---

## 9. Enhancement backlog (post-hackathon: making it genuinely useful in the real world)

**Intake & integrations**
- Linear / Jira / Sentry / support-ticket intake (a Sentry stack trace is a bug claim too — richer than most issues).
- Slack/Teams notifications with verdict summaries; weekly "backlog health" digest for maintainers.
- GitHub **Checks** integration: run Module E (AI-PR audit) as a required status check — "evidence-verified" as a merge gate.
- **MCP server** exposing the evidence engine as tools (`reproduce(issue_url)`, `verify(pr_url)`) so *other* agents — Claude Code, Codex, Copilot — can call Reprove as their verification oracle. Turns competitors into customers.

**Reliability & scale**
- **Environment recipe cache:** every successful bootstrap stored per-repo; recipes aggregate across users into a build-knowledge database — the long-term data moat (the accumulated version of "reliably building arbitrary repos," which nobody starts with).
- Monorepo support (per-package scoping); private registry auth; resource budgeting + per-issue cost caps; queueing/parallelism.
- Confidence calibration from outcomes: track which evidence bundles get merged vs. rejected; recalibrate the score.

**Product depth**
- **Duplicate detection by evidence:** two issues whose generated repro tests fail identically are duplicates — dedup by execution, not text similarity (nobody does this).
- Reporter dialogue loop: `NEEDS_INFO` questions posted, answers ingested, reproduction retried automatically.
- Flaky quarantine integration (Module D) wired to CI providers.
- Security advisory intake (Module C) with minimum-viable-upgrade planner.
- Regression sentinel (Module F) as a scheduled weekly job.
- Multi-language expansion order: Python/TS → Java (biggest migration budgets) → Go.
- "Reproduced ✅ by Reprove" badge + free tier for public repos — every badge on a popular OSS issue is distribution.
- Org policy file (`.reprove.yml`): autonomy tier, cost caps, protected paths, test conventions.
- Longitudinal repo health dashboard: reproduce-rate trends, evidence-coverage of the backlog, mean-time-to-triage.

**Honest known limitations (list these; it builds trust)**
- Environment bootstrapping outside the supported tier fails gracefully but often.
- UI/visual bugs need browser automation (Playwright) — roadmap, not launch.
- Heisenbugs/concurrency bugs may defeat determinism screening (future: record-replay execution).
- Long test suites make blast-radius checks expensive — mitigated by nearest-neighbor selection.

---

## 10. Project summary (for Devpost / README)

**Short (1–2 sentences):**
> Reprove is a verification-first maintenance agent: it turns vague bug reports and risky dependency upgrades into executable proof — failing tests generated, run, and validated in a sandbox — and refuses to fix anything it can't first prove is broken. While every other AI agent races to write more code, Reprove is the trust layer that proves code: evidence-gated fixes, canary tests that catch silent upgrade breakage, and triage verdicts backed by real execution instead of plausible text.

**One-liner variant (for the header field):**
> The AI agent that proves bugs before anyone fixes them — no fix without a failing test.