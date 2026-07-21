# Operating Reprove

## Local evidence cockpit

```bash
python -m pip install -e '.[dev]'
reprove-api
```

Open `http://127.0.0.1:8000`. The **Start evidence run** form is deliberately
development-only: it submits the seeded local checkout through the same durable
run/event/artifact pipeline used by hosted jobs.

## Container control plane

```bash
docker compose up --build
```

This starts the FastAPI control plane, PostgreSQL, Redis, and a separate queue
worker with a persistent artifact volume. The API automatically switches to
Redis queueing when `REPROVE_REDIS_URL` is set; the worker consumes the same
versioned issue/upgrade job payloads. The compose file is for local evaluation;
production requires managed Postgres, object storage, TLS, and secret management.

Set `REPROVE_API_TOKEN` in every deployed environment. Mutating control-plane
endpoints then require `Authorization: Bearer <token>`; local development leaves
it unset. GitHub webhooks are separately authenticated with their HMAC secret.

## GitHub App wiring

Configure `REPROVE_GITHUB_APP_ID`, `REPROVE_GITHUB_APP_PRIVATE_KEY`, and the
webhook target `/v1/github/webhooks` with `REPROVE_GITHUB_WEBHOOK_SECRET`.
Reprove signs a short-lived App JWT and exchanges it for a GitHub installation
token only when it needs repository access; neither the private key nor tokens
are persisted in the database or evidence bundle. Request only repository
metadata, contents, issues, checks, and pull-request permissions. GitHub
delivery IDs are persisted and deduplicated before any trigger routing. The
current endpoint recognizes:

- applying the `reprove` label to an issue;
- commenting `@reprove reproduce this` on an issue;
- bot-authored pull-request events for the future AI-PR audit queue.

An actionable event for a connected repository creates an `awaiting_review`
intake only. A maintainer still must select a pinned checkout and narrow command;
no webhook can launch a test run or publish a GitHub change by itself.

## Managed isolated runners

Register a managed runner with explicit capabilities, for example
`{"network_isolated": true, "read_only_source": true}`. A repository in
`managed` mode only leases jobs to an enrolled managed runner whose capabilities
match the job requirements. The lease records the runner id, and completion is
accepted only from that same token holder via
`POST /v1/runners/{runner_id}/runs/{run_id}/complete`.

Do not mount GitHub or provider credentials in a repository execution sandbox.
The runner obtains any short-lived checkout credential before the container is
sealed, then runs build/test with no network, a read-only source mount, dropped
Linux capabilities, no-new-privileges, and CPU/memory caps. The runner returns
only a redacted evidence bundle to the control plane.

## Retention and incident response

Evidence artifacts are redacted before persistence and are configured for a
30-day hosted retention policy. In production, run a daily deletion job against
the artifact store and database, preserve an organization audit record of the
deletion, and allow an owner to export or delete organization data on demand.
