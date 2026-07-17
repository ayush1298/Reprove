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

Configure the webhook target as `/v1/github/webhooks`, set
`REPROVE_GITHUB_WEBHOOK_SECRET`, and request only repository metadata, contents,
issues, checks, and pull-request permissions. GitHub delivery IDs are persisted
and deduplicated before any trigger routing. The current endpoint recognizes:

- applying the `reprove` label to an issue;
- commenting `@reprove reproduce this` on an issue;
- bot-authored pull-request events for the future AI-PR audit queue.

Do not mount GitHub or provider credentials in a repository execution sandbox.
The worker must obtain a fresh short-lived token, clone the requested commit, and
then seal network access for build/test execution.

## Retention and incident response

Evidence artifacts are redacted before persistence and are configured for a
30-day hosted retention policy. In production, run a daily deletion job against
the artifact store and database, preserve an organization audit record of the
deletion, and allow an owner to export or delete organization data on demand.
