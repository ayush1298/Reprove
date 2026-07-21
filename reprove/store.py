"""Persistence boundary for runs, events, repositories, and immutable evidence artifacts."""

from __future__ import annotations

import json
import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from .database import ArtifactRecord, Database, GitHubInstallationRecord, IntegrationEventRecord, OrganizationRecord, RepositoryRecord, RunEventRecord, RunRecord, RunnerRecord, WebhookDeliveryRecord, utcnow
from .models import EvidenceBundle
from .redaction import redact_value


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class RunStore:
    def __init__(self, database: Database, artifact_root: Path):
        self.database = database
        self.artifact_root = artifact_root
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def ensure_organization(self, slug: str, name: str | None = None) -> OrganizationRecord:
        with self.database.session() as session:
            item = session.scalar(select(OrganizationRecord).where(OrganizationRecord.slug == slug))
            if not item:
                item = OrganizationRecord(slug=slug, name=name or slug)
                session.add(item); session.commit()
            return item

    def ensure_repository(self, organization_slug: str, full_name: str, **values: Any) -> RepositoryRecord:
        organization = self.ensure_organization(organization_slug)
        with self.database.session() as session:
            item = session.scalar(select(RepositoryRecord).where(RepositoryRecord.full_name == full_name))
            if not item:
                item = RepositoryRecord(organization_id=organization.id, full_name=full_name, **values)
                session.add(item); session.commit()
            return item

    def create_run(self, repository_id: str, *, kind: str, claim: str, source: dict | None = None, request: dict | None = None) -> RunRecord:
        with self.database.session() as session:
            run = RunRecord(repository_id=repository_id, kind=kind, claim=claim, source=source or {}, request=request or {})
            session.add(run); session.commit(); session.refresh(run)
            self._event(session, run, "run.queued", "Run queued for execution.")
            session.commit()
            return run

    def _event(self, session, run: RunRecord, event_type: str, message: str, payload: dict | None = None) -> RunEventRecord:
        sequence = (session.scalar(select(func.max(RunEventRecord.sequence)).where(RunEventRecord.run_id == run.id)) or 0) + 1
        event = RunEventRecord(run_id=run.id, sequence=sequence, type=event_type, message=message, payload=payload or {})
        session.add(event)
        return event

    def transition(self, run_id: str, status: str, message: str, payload: dict | None = None) -> None:
        with self.database.session() as session:
            run = session.get(RunRecord, run_id)
            if not run or run.status in TERMINAL_STATUSES:
                return
            run.status = status
            if status == "running" and not run.started_at:
                run.started_at = utcnow()
            if status in TERMINAL_STATUSES:
                run.finished_at = utcnow()
            self._event(session, run, f"run.{status}", message, payload)
            session.commit()

    def complete(self, run_id: str, bundle: EvidenceBundle, summary: str) -> None:
        with self.database.session() as session:
            run = session.get(RunRecord, run_id)
            if not run:
                return
            run.status = "completed"
            run.verdict = bundle.verdict.value
            run.confidence = bundle.confidence
            run.summary = summary
            run.finished_at = utcnow()
            self._event(session, run, "run.completed", "Evidence bundle finalized.", {"verdict": run.verdict, "confidence": run.confidence})
            for integration_event in session.scalars(select(IntegrationEventRecord).where(IntegrationEventRecord.run_id == run_id)):
                integration_event.status = "resolved"
                integration_event.result = {"verdict": run.verdict, "confidence": run.confidence, "summary": summary}
            session.commit()
        target = self.artifact_root / run_id
        target.mkdir(parents=True, exist_ok=True)
        bundle_path = target / "evidence.json"
        safe_bundle = redact_value(bundle.as_dict())
        rendered = json.dumps(safe_bundle, indent=2, default=str) + "\n"
        bundle_path.write_text(rendered)
        digest = hashlib.sha256(json.dumps(safe_bundle, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        manifest_path = target / "manifest.json"
        manifest_path.write_text(json.dumps({"schema_version": 1, "run_id": run_id, "artifact": "evidence.json", "sha256": digest, "created_at": utcnow().isoformat()}, indent=2) + "\n")
        with self.database.session() as session:
            repo = session.get(RepositoryRecord, run.repository_id)
            organization = session.get(OrganizationRecord, repo.organization_id) if repo else None
            expires_at = utcnow() + timedelta(days=organization.retention_days if organization else 30)
            artifact = ArtifactRecord(run_id=run_id, kind="evidence_bundle", uri=str(bundle_path), size_bytes=bundle_path.stat().st_size, expires_at=expires_at)
            session.add(artifact); session.commit()
            session.add(ArtifactRecord(run_id=run_id, kind="evidence_manifest", uri=str(manifest_path), size_bytes=manifest_path.stat().st_size, expires_at=expires_at))
            session.commit()

    def fail(self, run_id: str, message: str, detail: str = "") -> None:
        with self.database.session() as session:
            run = session.get(RunRecord, run_id)
            if not run:
                return
            run.status = "failed"; run.summary = message; run.finished_at = utcnow()
            self._event(session, run, "run.failed", message, {"detail": detail[-4000:]})
            for integration_event in session.scalars(select(IntegrationEventRecord).where(IntegrationEventRecord.run_id == run_id)):
                integration_event.status = "failed"
                integration_event.result = {"summary": message}
            session.commit()

    def cancel(self, run_id: str) -> bool:
        with self.database.session() as session:
            run = session.get(RunRecord, run_id)
            if not run or run.status in TERMINAL_STATUSES:
                return False
            run.cancel_requested = True
            self._event(session, run, "run.cancel_requested", "Cancellation requested by user.")
            session.commit(); return True

    def get_run(self, run_id: str) -> RunRecord | None:
        with self.database.session() as session:
            return session.get(RunRecord, run_id)

    def list_runs(self, repository_id: str | None = None, limit: int = 50) -> list[RunRecord]:
        with self.database.session() as session:
            stmt = select(RunRecord).order_by(RunRecord.created_at.desc()).limit(limit)
            if repository_id:
                stmt = stmt.where(RunRecord.repository_id == repository_id)
            return list(session.scalars(stmt))

    def events(self, run_id: str, after: int = 0) -> list[RunEventRecord]:
        with self.database.session() as session:
            return list(session.scalars(select(RunEventRecord).where(RunEventRecord.run_id == run_id, RunEventRecord.sequence > after).order_by(RunEventRecord.sequence)))

    def bundle_path(self, run_id: str) -> Path | None:
        with self.database.session() as session:
            artifact = session.scalar(select(ArtifactRecord).where(ArtifactRecord.run_id == run_id, ArtifactRecord.kind == "evidence_bundle"))
            return Path(artifact.uri) if artifact else None

    def record_webhook_delivery(self, delivery_id: str, event: str, payload: dict) -> bool:
        """Returns false for a duplicate delivery, making GitHub retries idempotent."""
        with self.database.session() as session:
            if session.scalar(select(WebhookDeliveryRecord).where(WebhookDeliveryRecord.delivery_id == delivery_id)):
                return False
            session.add(WebhookDeliveryRecord(delivery_id=delivery_id, event=event, payload=payload))
            session.commit()
            return True

    def create_integration_event(self, *, provider: str, kind: str, external_ref: str, title: str, claim: str = "", repository_id: str | None = None, external_url: str | None = None, fingerprint: str | None = None, severity: str | None = None, payload: dict | None = None, result: dict | None = None) -> IntegrationEventRecord:
        """Persist a received integration signal. This method never talks to the provider."""
        with self.database.session() as session:
            event = IntegrationEventRecord(repository_id=repository_id, provider=provider, kind=kind, external_ref=external_ref, title=title, claim=claim, external_url=external_url, fingerprint=fingerprint, severity=severity, payload=redact_value(payload or {}), result=result or {})
            session.add(event); session.commit(); session.refresh(event)
            return event

    def list_integration_events(self, repository_id: str | None = None, limit: int = 100) -> list[IntegrationEventRecord]:
        with self.database.session() as session:
            stmt = select(IntegrationEventRecord).order_by(IntegrationEventRecord.created_at.desc()).limit(limit)
            if repository_id:
                stmt = stmt.where(IntegrationEventRecord.repository_id == repository_id)
            return list(session.scalars(stmt))

    def attach_event_run(self, event_id: str, run_id: str) -> IntegrationEventRecord | None:
        with self.database.session() as session:
            event = session.get(IntegrationEventRecord, event_id)
            if not event:
                return None
            event.run_id, event.status = run_id, "running"
            session.commit(); session.refresh(event)
            return event

    def resolve_integration_event(self, event_id: str, *, status: str, result: dict) -> IntegrationEventRecord | None:
        with self.database.session() as session:
            event = session.get(IntegrationEventRecord, event_id)
            if not event:
                return None
            event.status, event.result = status, redact_value(result)
            session.commit(); session.refresh(event)
            return event

    def purge_expired_artifacts(self) -> int:
        """Retention worker entry point. Deletes local objects only after their expiry timestamp."""
        with self.database.session() as session:
            expired = list(session.scalars(select(ArtifactRecord).where(ArtifactRecord.expires_at.is_not(None), ArtifactRecord.expires_at <= utcnow())))
            for artifact in expired:
                path = Path(artifact.uri)
                if path.exists():
                    path.unlink()
                session.delete(artifact)
            session.commit()
            return len(expired)

    def register_runner(self, organization_id: str, name: str, mode: str, capabilities: dict, lease_token_hash: str) -> RunnerRecord:
        with self.database.session() as session:
            item = RunnerRecord(organization_id=organization_id, name=name, mode=mode, capabilities=redact_value(capabilities), lease_token_hash=lease_token_hash)
            session.add(item); session.commit(); session.refresh(item)
            return item

    def heartbeat_runner(self, runner_id: str, lease_token_hash: str) -> RunnerRecord | None:
        with self.database.session() as session:
            item = session.get(RunnerRecord, runner_id)
            if not item or item.lease_token_hash != lease_token_hash:
                return None
            item.last_seen_at = utcnow(); session.commit(); session.refresh(item)
            return item

    @staticmethod
    def _capabilities_match(requirements: dict, capabilities: dict) -> bool:
        """Use a deliberately small, auditable matching rule for isolated runners."""
        for key, required in requirements.items():
            actual = capabilities.get(key)
            if isinstance(required, list):
                if not isinstance(actual, list) or not set(required).issubset(set(actual)):
                    return False
            elif actual != required:
                return False
        return True

    def lease_next_run(self, runner_id: str, lease_token_hash: str) -> RunRecord | None:
        """Atomically claim the oldest organization job compatible with this runner."""
        with self.database.session() as session:
            runner = session.get(RunnerRecord, runner_id)
            if not runner or runner.lease_token_hash != lease_token_hash:
                return None
            queued = list(session.scalars(
                select(RunRecord)
                .join(RepositoryRecord, RepositoryRecord.id == RunRecord.repository_id)
                .where(RepositoryRecord.organization_id == runner.organization_id, RepositoryRecord.runner_mode == runner.mode, RunRecord.status == "queued")
                .order_by(RunRecord.created_at)
            ))
            run = next((item for item in queued if self._capabilities_match(item.request.get("runner_requirements", {}), runner.capabilities)), None)
            if not run:
                return None
            run.status = "running"; run.started_at = utcnow(); run.leased_runner_id = runner_id
            self._event(session, run, "run.leased", "Isolated runner leased run.", {"runner_id": runner_id, "mode": runner.mode, "requirements": run.request.get("runner_requirements", {})})
            session.commit(); session.refresh(run)
            return run

    def complete_leased_run(self, runner_id: str, lease_token_hash: str, run_id: str, bundle: EvidenceBundle, summary: str) -> bool:
        """Accept completion only from the runner which holds the active lease."""
        with self.database.session() as session:
            runner, run = session.get(RunnerRecord, runner_id), session.get(RunRecord, run_id)
            if not runner or not run or runner.lease_token_hash != lease_token_hash or run.leased_runner_id != runner_id or run.status != "running" or run.cancel_requested or bundle.claim != run.claim:
                return False
            self._event(session, run, "run.runner_completion_received", "Runner submitted an evidence bundle.", {"runner_id": runner_id})
            session.commit()
        self.complete(run_id, bundle, summary)
        return True

    def list_runners(self, organization_id: str | None = None, limit: int = 100) -> list[RunnerRecord]:
        with self.database.session() as session:
            statement = select(RunnerRecord).order_by(RunnerRecord.last_seen_at.desc()).limit(limit)
            if organization_id:
                statement = statement.where(RunnerRecord.organization_id == organization_id)
            return list(session.scalars(statement))

    def upsert_github_installation(self, organization_id: str, github_installation_id: str, login: str, permissions: dict) -> GitHubInstallationRecord:
        with self.database.session() as session:
            item = session.scalar(select(GitHubInstallationRecord).where(GitHubInstallationRecord.github_installation_id == str(github_installation_id)))
            if not item:
                item = GitHubInstallationRecord(organization_id=organization_id, github_installation_id=str(github_installation_id), github_account_login=login, permissions=permissions)
                session.add(item)
            else:
                item.organization_id, item.github_account_login, item.permissions = organization_id, login, permissions
            session.commit(); session.refresh(item)
            return item

    def github_installation(self, github_installation_id: str) -> GitHubInstallationRecord | None:
        with self.database.session() as session:
            return session.scalar(select(GitHubInstallationRecord).where(GitHubInstallationRecord.github_installation_id == str(github_installation_id)))
