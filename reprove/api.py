"""FastAPI control plane for Reprove's evidence-first workflows."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from .database import Database, OrganizationRecord, RepositoryRecord, RunRecord
from .github_events import normalize_trigger
from .orchestrator import LocalJobDispatcher
from .jobs import RedisJobDispatcher
from .store import RunStore
from .models import ChangeSet
from .workflows import UpgradeProposal
from .runners import new_lease, token_hash
from .security import require_control_plane_access
from .audit import audit_pull_request
from .models import EvidenceBundle, Verdict
from .benchmark import READ_ONLY_GUARANTEE, load_manifest
from .github import fetch_public_issue
from .integrations import as_dict, normalize_signal


class OrganizationInput(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,118}$")
    name: str = Field(min_length=2, max_length=200)


class RepositoryInput(BaseModel):
    organization_slug: str
    full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    default_branch: str = "main"
    runner_mode: Literal["hosted", "self-hosted"] = "hosted"
    policy: dict = Field(default_factory=dict)


class IssueRunInput(BaseModel):
    repository_id: str
    claim: str = Field(min_length=3, max_length=10000)
    repository_path: str = Field(min_length=1, max_length=2000, description="Development-only local checkout path")
    evidence_tests: list[str] = Field(default_factory=list, max_length=3)
    test_command: list[str] = Field(default_factory=list, max_length=30)
    questions: list[str] = Field(default_factory=list, max_length=5)
    issue_number: int | None = Field(default=None, ge=1)


class IssuePreviewInput(BaseModel):
    issue_url: str = Field(min_length=30, max_length=500)


class UpgradeRunInput(BaseModel):
    repository_id: str
    repository_path: str = Field(min_length=1, max_length=2000)
    dependency: str = Field(min_length=1, max_length=200)
    old_version: str = Field(min_length=1, max_length=100)
    new_version: str = Field(min_length=1, max_length=100)
    files: dict[str, str] = Field(min_length=1)
    canary_tests: list[str] = Field(min_length=1, max_length=3)
    canary_command: list[str] = Field(min_length=1, max_length=30)
    nearby_command: list[str] | None = Field(default=None, max_length=30)
    changelog_notes: str = Field(default="", max_length=10000)


class RunnerRegistrationInput(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=200)
    capabilities: dict = Field(default_factory=dict)


class PullRequestAuditInput(BaseModel):
    repository_id: str | None = None
    pull_request_number: int | None = Field(default=None, ge=1)
    head_sha: str | None = Field(default=None, max_length=100)
    evidence_run_id: str | None = None
    linked_issue: bool
    unified_diff: str = Field(max_length=500000)
    regression_clean: bool = True


class IntegrationIntakeInput(BaseModel):
    provider: Literal["sentry", "linear", "jira", "github"]
    external_ref: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=10000)
    claim: str = Field(default="", max_length=20000)
    repository_id: str | None = None
    external_url: str | None = Field(default=None, max_length=2000)
    fingerprint: str | None = Field(default=None, max_length=300)
    severity: str | None = Field(default=None, max_length=40)
    payload: dict = Field(default_factory=dict)


class IntegrationEvidenceRunInput(IssueRunInput):
    pass


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict = Field(default_factory=dict)


def run_payload(run: RunRecord) -> dict:
    return {
        "id": run.id, "repository_id": run.repository_id, "kind": run.kind, "status": run.status,
        "verdict": run.verdict, "claim": run.claim, "source": run.source, "summary": run.summary,
        "confidence": run.confidence, "cancel_requested": run.cancel_requested,
        "created_at": run.created_at.isoformat(), "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def repo_payload(repo: RepositoryRecord) -> dict:
    return {"id": repo.id, "organization_id": repo.organization_id, "full_name": repo.full_name, "default_branch": repo.default_branch, "runner_mode": repo.runner_mode, "policy": repo.policy}


class AppState:
    def __init__(self, database_url: str, artifact_root: Path):
        self.database = Database(database_url)
        self.store = RunStore(self.database, artifact_root)
        redis_url = os.environ.get("REPROVE_REDIS_URL")
        self.dispatcher = RedisJobDispatcher(redis_url) if redis_url else LocalJobDispatcher(self.store)


def create_app(database_url: str | None = None, artifact_root: str | Path | None = None) -> FastAPI:
    root = Path(artifact_root or os.environ.get("REPROVE_ARTIFACT_ROOT", ".reprove-service/artifacts"))
    state = AppState(database_url or os.environ.get("REPROVE_DATABASE_URL", "sqlite:///./reprove.db"), root)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state.database.create_all()
        app.state.reprove = state
        yield

    app = FastAPI(title="Reprove Control Plane", version="0.2.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("REPROVE_CORS_ORIGINS", "http://localhost:8000").split(","), allow_methods=["GET", "POST", "PUT"], allow_headers=["*"], allow_credentials=True)

    def get_state() -> AppState:
        return app.state.reprove

    def integration_payload(event) -> dict:
        return {
            "id": event.id, "provider": event.provider, "kind": event.kind, "external_ref": event.external_ref,
            "title": event.title, "claim": event.claim, "repository_id": event.repository_id, "external_url": event.external_url,
            "fingerprint": event.fingerprint, "severity": event.severity, "status": event.status, "run_id": event.run_id,
            "result": event.result, "created_at": event.created_at.isoformat(), "updated_at": event.updated_at.isoformat(),
        }

    def audit_result_payload(payload: PullRequestAuditInput, service: AppState) -> dict:
        evidence = None
        if payload.evidence_run_id:
            path = service.store.bundle_path(payload.evidence_run_id)
            if not path or not path.exists():
                raise HTTPException(status_code=404, detail="Evidence run has no persisted bundle.")
            data = json.loads(path.read_text())
            evidence = EvidenceBundle(data["repository"], data["claim"], Verdict(data["verdict"]), confidence=data.get("confidence", 0))
        result = audit_pull_request(linked_issue=payload.linked_issue, evidence=evidence, unified_diff=payload.unified_diff, regression_clean=payload.regression_clean)
        return {"decision": result.decision.value, "confidence": result.confidence, "findings": [{"code": item.code, "message": item.message, "severity": item.severity} for item in result.findings]}

    def queue_issue_run(payload: IssueRunInput, service: AppState, *, start: bool = True):
        with service.database.session() as session:
            repository = session.get(RepositoryRecord, payload.repository_id)
            if not repository:
                raise HTTPException(status_code=404, detail="Repository not found.")
        run = service.store.create_run(payload.repository_id, kind="issue_prover", claim=payload.claim, source={"issue_number": payload.issue_number}, request=payload.model_dump())
        if start and repository.runner_mode == "hosted":
            service.dispatcher.submit_issue(run.id, payload.repository_path, payload.claim, payload.evidence_tests, payload.test_command, payload.questions)
        return run

    @app.get("/health")
    def health(service=Depends(get_state)):
        return {"status": "ok", "database": service.database.engine.url.get_backend_name(), "retention_days": 30}

    @app.post("/v1/organizations", status_code=status.HTTP_201_CREATED)
    def create_organization(payload: OrganizationInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        org = service.store.ensure_organization(payload.slug, payload.name)
        return {"id": org.id, "slug": org.slug, "name": org.name, "retention_days": org.retention_days}

    @app.post("/v1/repositories", status_code=status.HTTP_201_CREATED)
    def create_repository(payload: RepositoryInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        try:
            repo = service.store.ensure_repository(payload.organization_slug, payload.full_name, default_branch=payload.default_branch, runner_mode=payload.runner_mode, policy=payload.policy)
        except Exception as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return repo_payload(repo)

    @app.get("/v1/repositories")
    def list_repositories(service=Depends(get_state)):
        with service.database.session() as session:
            return [repo_payload(item) for item in session.scalars(select(RepositoryRecord).order_by(RepositoryRecord.full_name))]

    @app.post("/v1/runs/issue-prover", status_code=status.HTTP_202_ACCEPTED)
    def create_issue_run(payload: IssueRunInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        run = queue_issue_run(payload, service)
        return run_payload(run)

    @app.get("/v1/runs")
    def list_runs(repository_id: str | None = None, limit: int = 50, service: AppState = Depends(get_state)):
        return [run_payload(run) for run in service.store.list_runs(repository_id, min(max(limit, 1), 100))]

    @app.post("/v1/runs/upgrade-verifier", status_code=status.HTTP_202_ACCEPTED)
    def create_upgrade_run(payload: UpgradeRunInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        with service.database.session() as session:
            repository = session.get(RepositoryRecord, payload.repository_id)
            if not repository:
                raise HTTPException(status_code=404, detail="Repository not found.")
        claim = f"Upgrading {payload.dependency} from {payload.old_version} to {payload.new_version} preserves pinned behavior."
        run = service.store.create_run(payload.repository_id, kind="upgrade_verifier", claim=claim, request=payload.model_dump())
        proposal = UpgradeProposal(payload.dependency, payload.old_version, payload.new_version, ChangeSet(payload.files, f"Upgrade {payload.dependency}"), payload.canary_tests, payload.canary_command, payload.changelog_notes)
        if repository.runner_mode == "hosted":
            service.dispatcher.submit_upgrade(run.id, payload.repository_path, proposal, payload.nearby_command)
        return run_payload(run)

    @app.post("/v1/runners", status_code=status.HTTP_201_CREATED)
    def register_runner(payload: RunnerRegistrationInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        with service.database.session() as session:
            if not session.get(OrganizationRecord, payload.organization_id):
                raise HTTPException(status_code=404, detail="Organization not found.")
        lease = new_lease("pending")
        runner = service.store.register_runner(payload.organization_id, payload.name, payload.capabilities, token_hash(lease.token))
        return {"runner_id": runner.id, "lease_token": lease.token, "expires_in_seconds": lease.expires_in_seconds}

    @app.post("/v1/runners/{runner_id}/heartbeat")
    def heartbeat_runner(runner_id: str, request: Request, service=Depends(get_state)):
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        runner = service.store.heartbeat_runner(runner_id, token_hash(token)) if token else None
        if not runner:
            raise HTTPException(status_code=401, detail="Invalid runner lease token.")
        return {"runner_id": runner.id, "last_seen_at": runner.last_seen_at.isoformat(), "capabilities": runner.capabilities}

    @app.post("/v1/runners/{runner_id}/leases")
    def lease_run(runner_id: str, request: Request, service=Depends(get_state)):
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        run = service.store.lease_next_run(runner_id, token_hash(token)) if token else None
        if not run:
            return JSONResponse(status_code=204, content=None)
        return run_payload(run) | {"job": run.request}

    @app.post("/v1/audits/pull-request")
    def audit_pr(payload: PullRequestAuditInput, service=Depends(get_state)):
        return audit_result_payload(payload, service)

    @app.post("/v1/integrations/github/pr-check", status_code=status.HTTP_201_CREATED)
    def github_pr_check(payload: PullRequestAuditInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        """Record a PR evidence check locally; no GitHub check, comment, or PR is created."""
        if not payload.repository_id:
            raise HTTPException(status_code=422, detail="repository_id is required to record a PR check.")
        with service.database.session() as session:
            if not session.get(RepositoryRecord, payload.repository_id):
                raise HTTPException(status_code=404, detail="Repository not found.")
        result = audit_result_payload(payload, service)
        event = service.store.create_integration_event(provider="github", kind="pull_request_check", external_ref=f"PR-{payload.pull_request_number or 'local'}", title=f"PR evidence check #{payload.pull_request_number or 'local'}", claim="Independent evidence audit for a proposed change.", repository_id=payload.repository_id, fingerprint=payload.head_sha, payload={"linked_issue": payload.linked_issue, "evidence_run_id": payload.evidence_run_id}, result=result)
        event = service.store.resolve_integration_event(event.id, status="verified" if result["decision"] == "VERIFIED" else "needs_review", result=result) or event
        return integration_payload(event)

    @app.post("/v1/integrations/intake", status_code=status.HTTP_201_CREATED)
    def create_integration_intake(payload: IntegrationIntakeInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        if payload.repository_id:
            with service.database.session() as session:
                if not session.get(RepositoryRecord, payload.repository_id):
                    raise HTTPException(status_code=404, detail="Repository not found.")
        event = service.store.create_integration_event(provider=payload.provider, kind="incident_intake", external_ref=payload.external_ref, title=payload.title, claim=payload.claim or payload.title, repository_id=payload.repository_id, external_url=payload.external_url, fingerprint=payload.fingerprint, severity=payload.severity, payload=payload.payload)
        return integration_payload(event)

    @app.post("/v1/integrations/{event_id}/evidence-run", status_code=status.HTTP_202_ACCEPTED)
    def integration_evidence_run(event_id: str, payload: IntegrationEvidenceRunInput, service=Depends(get_state), _=Depends(require_control_plane_access)):
        event = next((item for item in service.store.list_integration_events(limit=1000) if item.id == event_id), None)
        if not event:
            raise HTTPException(status_code=404, detail="Integration intake not found.")
        if event.repository_id and event.repository_id != payload.repository_id:
            raise HTTPException(status_code=422, detail="Evidence run repository must match the integration intake.")
        run = queue_issue_run(payload, service, start=False)
        service.store.attach_event_run(event_id, run.id)
        with service.database.session() as session:
            repository = session.get(RepositoryRecord, payload.repository_id)
        if repository and repository.runner_mode == "hosted":
            service.dispatcher.submit_issue(run.id, payload.repository_path, payload.claim, payload.evidence_tests, payload.test_command, payload.questions)
        return run_payload(run) | {"integration_event_id": event_id}

    @app.get("/v1/integrations")
    def list_integrations(repository_id: str | None = None, service=Depends(get_state)):
        return [integration_payload(event) for event in service.store.list_integration_events(repository_id, 100)]

    @app.post("/v1/integrations/webhooks/{provider}", status_code=status.HTTP_202_ACCEPTED)
    async def integration_webhook(provider: Literal["sentry", "linear", "jira", "github"], request: Request, service=Depends(get_state)):
        """Optional inbound webhook. Disabled unless the shared secret is explicitly configured."""
        secret = os.environ.get("REPROVE_INTEGRATION_WEBHOOK_SECRET")
        if not secret:
            raise HTTPException(status_code=503, detail="Inbound integration webhooks are disabled until REPROVE_INTEGRATION_WEBHOOK_SECRET is configured.")
        body = await request.body()
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request.headers.get("x-reprove-signature", "")):
            raise HTTPException(status_code=401, detail="Invalid integration webhook signature.")
        signal = normalize_signal(provider, json.loads(body or b"{}"))
        event = service.store.create_integration_event(**as_dict(signal), kind="incident_intake", payload=json.loads(body or b"{}"))
        return {"accepted": True, "event": integration_payload(event), "outbound_writes": False}

    @app.get("/v1/ledger")
    def evidence_ledger(repository_id: str | None = None, service=Depends(get_state)):
        runs = service.store.list_runs(repository_id, 100)
        events = service.store.list_integration_events(repository_id, 100)
        return {
            "summary": {"runs": len(runs), "bundles": sum(bool(service.store.bundle_path(run.id)) for run in runs), "open_intakes": sum(event.status in {"intake", "running", "needs_review"} for event in events), "resolved_intakes": sum(event.status in {"resolved", "verified"} for event in events)},
            "runs": [run_payload(run) | {"bundle_available": bool(service.store.bundle_path(run.id))} for run in runs],
            "integrations": [integration_payload(event) for event in events],
        }

    @app.post("/mcp")
    def mcp(request: MCPRequest, service=Depends(get_state)):
        """Small Streamable-HTTP MCP surface for coding agents; all writes stay local to Reprove."""
        if request.jsonrpc != "2.0":
            raise HTTPException(status_code=400, detail="MCP requests must use JSON-RPC 2.0.")
        if request.method == "initialize":
            return {"jsonrpc": "2.0", "result": {"protocolVersion": "2025-03-26", "serverInfo": {"name": "reprove", "version": "0.2.0"}, "capabilities": {"tools": {}}}}
        if request.method == "tools/list":
            tools = [
                {"name": "reprove_audit_pr", "description": "Audit a pull-request diff against a Reprove evidence run. Never posts to GitHub.", "inputSchema": {"type": "object", "required": ["linked_issue", "unified_diff"], "properties": {"linked_issue": {"type": "boolean"}, "unified_diff": {"type": "string"}, "evidence_run_id": {"type": "string"}, "regression_clean": {"type": "boolean"}}}},
                {"name": "reprove_replay_bundle", "description": "Read an immutable local evidence bundle by run id.", "inputSchema": {"type": "object", "required": ["run_id"], "properties": {"run_id": {"type": "string"}}}},
                {"name": "reprove_ledger", "description": "List recent proof runs and external intake outcomes.", "inputSchema": {"type": "object", "properties": {"repository_id": {"type": "string"}}}},
            ]
            return {"jsonrpc": "2.0", "result": {"tools": tools}}
        if request.method == "tools/call":
            name, arguments = request.params.get("name"), request.params.get("arguments", {})
            if name == "reprove_audit_pr":
                result = audit_result_payload(PullRequestAuditInput(**arguments), service)
            elif name == "reprove_replay_bundle":
                path = service.store.bundle_path(arguments.get("run_id", ""))
                if not path or not path.exists():
                    raise HTTPException(status_code=404, detail="Evidence bundle is not available yet.")
                result = json.loads(path.read_text())
            elif name == "reprove_ledger":
                result = evidence_ledger(arguments.get("repository_id"), service)
            else:
                raise HTTPException(status_code=404, detail="Unknown MCP tool.")
            return {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}}
        raise HTTPException(status_code=404, detail="Unsupported MCP method.")

    @app.get("/v1/repositories/{repository_id}/health")
    def repository_health(repository_id: str, service=Depends(get_state)):
        with service.database.session() as session:
            if not session.get(RepositoryRecord, repository_id):
                raise HTTPException(status_code=404, detail="Repository not found.")
        runs = service.store.list_runs(repository_id, 100)
        completed = [run for run in runs if run.status == "completed"]
        reproduced = [run for run in completed if run.verdict in {"REPRODUCED", "FIX_VERIFIED"}]
        return {"repository_id": repository_id, "runs": len(runs), "completed": len(completed), "reproduce_rate": round(100 * len(reproduced) / len(completed), 1) if completed else None, "environment_blockers": sum(run.verdict == "ENV_UNSUPPORTED" for run in completed), "average_confidence": round(sum(run.confidence for run in completed) / len(completed), 1) if completed else None}

    @app.get("/v1/runs/{run_id}")
    def get_run(run_id: str, service=Depends(get_state)):
        run = service.store.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found.")
        output = run_payload(run)
        output["events"] = [{"sequence": event.sequence, "type": event.type, "message": event.message, "payload": event.payload, "created_at": event.created_at.isoformat()} for event in service.store.events(run_id)]
        return output

    @app.post("/v1/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
    def cancel_run(run_id: str, service=Depends(get_state), _=Depends(require_control_plane_access)):
        if not service.store.cancel(run_id):
            raise HTTPException(status_code=409, detail="Run cannot be cancelled.")
        return {"id": run_id, "status": "cancellation_requested"}

    @app.get("/v1/runs/{run_id}/bundle")
    def get_bundle(run_id: str, service=Depends(get_state)):
        path = service.store.bundle_path(run_id)
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail="Evidence bundle is not available yet.")
        return JSONResponse(json.loads(path.read_text()))

    @app.get("/v1/runs/{run_id}/events")
    async def run_events(run_id: str, after: int = 0, service: AppState = Depends(get_state)):
        if not service.store.get_run(run_id):
            raise HTTPException(status_code=404, detail="Run not found.")

        async def stream():
            cursor = after
            for _ in range(120):  # five minutes; client reconnects with Last-Event-ID after that.
                events = service.store.events(run_id, cursor)
                for event in events:
                    cursor = event.sequence
                    payload = {"sequence": event.sequence, "type": event.type, "message": event.message, "payload": event.payload, "created_at": event.created_at.isoformat()}
                    yield f"id: {cursor}\nevent: {event.type}\ndata: {json.dumps(payload)}\n\n"
                run = service.store.get_run(run_id)
                if run and run.status in {"completed", "failed", "cancelled"}:
                    yield "event: end\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/v1/dashboard")
    def dashboard(service=Depends(get_state)):
        runs = service.store.list_runs(limit=100)
        verdicts: dict[str, int] = {}
        for run in runs:
            if run.verdict:
                verdicts[run.verdict] = verdicts.get(run.verdict, 0) + 1
        return {"runs": [run_payload(run) for run in runs[:12]], "metrics": {"total_runs": len(runs), "completed": sum(run.status == "completed" for run in runs), "verdicts": verdicts, "average_confidence": round(sum(run.confidence for run in runs) / len(runs), 1) if runs else None, "retention_days": 30}}

    @app.get("/v1/benchmarks")
    def benchmarks():
        """Expose intake metadata only; this endpoint cannot schedule external work."""
        manifest = Path(__file__).parent.parent / "benchmarks" / "candidates.jsonl"
        tasks = load_manifest(manifest) if manifest.exists() else []
        return {
            "read_only": True,
            "guarantee": READ_ONLY_GUARANTEE,
            "tasks": [{"id": task.id, "title": task.title, "repository": task.repository, "issue_url": task.issue_url, "status": task.status, "notes": task.notes} for task in tasks],
        }

    @app.post("/v1/github/issue-preview")
    def github_issue_preview(payload: IssuePreviewInput):
        """Read public issue metadata only; never creates any GitHub resource."""
        try:
            issue = fetch_public_issue(payload.issue_url)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "issue": {
                "repository": issue.repository, "number": issue.number, "title": issue.title, "body": issue.body,
                "html_url": issue.html_url, "state": issue.state, "labels": issue.labels, "author": issue.author, "updated_at": issue.updated_at,
            },
            "read_only": True,
            "guarantee": "This preview uses one anonymous GitHub GET request. It cannot create branches, commits, pull requests, comments, labels, or issue updates.",
            "stages": [
                {"id": "intake", "title": "Issue intake", "status": "complete", "detail": "Public title, description, labels, and provenance captured."},
                {"id": "review", "title": "Maintainer review", "status": "next", "detail": "Confirm the claim and choose a pinned local checkout."},
                {"id": "design", "title": "Evidence design", "status": "blocked", "detail": "Choose a narrow test and command; source tests remain immutable."},
                {"id": "execute", "title": "Isolated execution", "status": "blocked", "detail": "Run against the supplied local checkout and seal the evidence bundle."},
            ],
        }

    @app.post("/v1/github/webhooks", status_code=status.HTTP_202_ACCEPTED)
    async def github_webhook(request: Request, x_github_event: str = Header(default=""), x_hub_signature_256: str = Header(default="")):
        body = await request.body()
        secret = os.environ.get("REPROVE_GITHUB_WEBHOOK_SECRET")
        if secret:
            expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, x_hub_signature_256):
                raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature.")
        delivery_id = request.headers.get("x-github-delivery", hashlib.sha256(body).hexdigest())
        payload = json.loads(body or b"{}")
        service = app.state.reprove
        if not service.store.record_webhook_delivery(delivery_id, x_github_event, payload):
            return {"accepted": True, "duplicate": True, "delivery_id": delivery_id}
        trigger = normalize_trigger(x_github_event, payload)
        # The control plane records a verified delivery immediately. The GitHub worker
        # later resolves the installation to a checked-out commit before any execution.
        return {"accepted": True, "event": x_github_event, "delivery_id": delivery_id, "trigger": trigger.kind if trigger else None}

    dashboard_path = Path(__file__).parent.parent / "dashboard" / "index.html"
    @app.get("/", include_in_schema=False)
    def cockpit():
        return FileResponse(dashboard_path)

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("reprove.api:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=os.environ.get("REPROVE_RELOAD") == "1")
