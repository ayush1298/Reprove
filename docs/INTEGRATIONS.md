# Integrations guide

All integration surfaces are local-first and **never publish back to a provider automatically**.

## Cockpit flow

Open the **Integrations** page and choose one of these paths:

1. **Capture incident** — record a Sentry, Linear, Jira, or GitHub reference locally; then provide a local checkout, focused test, and command to queue evidence.
2. **Audit a PR** — submit a diff, optional evidence run id, and regression state. Reprove records a local `VERIFIED`, `WARNING`, or `REJECTED` decision; it does not post a GitHub check or comment.
3. **Run canary** — preserve an old-behavior test and apply a dependency bump only in a throwaway checkout.
4. **Evidence ledger** — see both external intake and durable evidence-bundle outcomes.

## Signed inbound webhooks

Set `REPROVE_INTEGRATION_WEBHOOK_SECRET`, then send JSON to:

```
POST /v1/integrations/webhooks/sentry
POST /v1/integrations/webhooks/linear
POST /v1/integrations/webhooks/jira
POST /v1/integrations/webhooks/github
```

Sign the exact request body using HMAC-SHA256 and send the result as `x-reprove-signature: sha256=<hex>`. A webhook is normalized into an intake record only; it cannot trigger an external write.

## MCP / agent API

`POST /mcp` implements JSON-RPC 2.0 methods `initialize`, `tools/list`, and `tools/call`.

Available tools:

- `reprove_audit_pr`
- `reprove_replay_bundle`
- `reprove_ledger`

Example discovery request:

```json
{"jsonrpc":"2.0","method":"tools/list"}
```
