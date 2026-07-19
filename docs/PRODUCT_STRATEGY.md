# Making Reprove useful beyond a demo

## The product promise

Reprove should be the independent evidence layer between an incoming claim or AI-generated change and a maintainer's merge button. Coding agents generate patches; observability products detect incidents; dependency bots make upgrades. Reprove earns its place by producing a replayable, policy-governed answer to: **did this exact behavior fail before the change, pass after it, resist a nearby counterexample, and stay inside a safe blast radius?**

## Next integrations to build

1. **Pull-request evidence check.** Accept a PR SHA from any author or coding agent, run the immutable evidence contract, and leave a check result—not an autonomous merge.
2. **Issue and incident intake.** Turn a GitHub issue, Sentry fingerprint, Linear/Jira ticket, or pasted stack trace into a proposed reproduction plan with a maintainer approval step.
3. **Dependency canaries.** Verify Dependabot/Renovate upgrades against preserved old-behavior tests and report a human-readable compatibility verdict.
4. **MCP/API evidence surface.** Let IDE and coding agents ask `reproduce`, `verify_change`, and `replay_bundle`, while Reprove retains authority over the gates.
5. **Evidence ledger.** Keep signed/redacted bundles, expiry, reruns after dependency changes, ownership, and a trend view of flaky or repeatedly-unprovable claims.

## Implemented integration surfaces

- **GitHub issue intake:** `POST /v1/github/issue-preview` reads one public issue with an anonymous `GET`, then the cockpit hands the maintainer to a local evidence run.
- **PR evidence check:** `POST /v1/integrations/github/pr-check` evaluates the supplied diff and optional evidence bundle, persists its decision in the ledger, and never posts a GitHub check or comment.
- **Upgrade canary:** `POST /v1/runs/upgrade-verifier` executes a preserved behavior test before and after a supplied dependency bump in a throwaway checkout.
- **Sentry, Linear, Jira, and GitHub intake:** `POST /v1/integrations/intake` supports reviewed/manual signals; signed `POST /v1/integrations/webhooks/{provider}` supports inbound automation when `REPROVE_INTEGRATION_WEBHOOK_SECRET` is configured. Neither performs outbound provider writes.
- **Agent/MCP surface:** `POST /mcp` implements JSON-RPC `initialize`, `tools/list`, and safe tools for PR audit, evidence-bundle replay, and ledger inspection.
- **Evidence ledger:** `GET /v1/ledger` joins durable runs, bundles, and external integration events; attached intakes resolve automatically when their evidence run completes.

## UX principle

The cockpit should answer “what needs my attention?” in seconds, then let a maintainer drill into an immutable bundle. It must distinguish live capability from roadmap items, explain refusal reasons, show source/commit provenance, and make the default action review—not publish. The new navigation exposes runs, evidence, benchmark safety, and repository policy as real destinations instead of decorative sidebar labels.

## End-to-end issue flow

1. Paste a canonical public GitHub issue URL in **Import GitHub issue**.
2. Reprove performs one anonymous `GET`, shows the captured title, body, labels, provenance, and the four execution stages.
3. The maintainer reviews the claim and explicitly supplies a local pinned checkout, an evidence test, and its command. Reprove does not clone the external repository in this flow.
4. The local isolated runner proves a deterministic failure, verifies the source-only change against immutable evidence, checks nearby mutations/blast radius, and seals a downloadable bundle.
5. The cockpit shows the outcome as `FIX_VERIFIED`, `REPRODUCED`, `NEEDS_INFO`, or a refusal—not an automatic PR or merge.

The preview endpoint has no token and no GitHub write methods. Its only remote operation is a single public issue `GET`.

## Guardrails that are product features

- No remote write from a benchmark run; no auto-created PR, branch, comment, or issue update.
- Source tests and protected paths remain immutable during fix verification.
- A passing fix is insufficient without a prior deterministic failure and an accepted gold/control result.
- Integrations should create drafts/checks and require explicit maintainer approval for external publication.
