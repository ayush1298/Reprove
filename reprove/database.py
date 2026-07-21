"""Durable control-plane entities. SQLite powers local mode; PostgreSQL uses the same schema."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class OrganizationRecord(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    repositories: Mapped[list["RepositoryRecord"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class RepositoryRecord(Base):
    __tablename__ = "repositories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    installation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    runner_mode: Mapped[str] = mapped_column(String(30), default="hosted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    organization: Mapped[OrganizationRecord] = relationship(back_populates="repositories")
    runs: Mapped[list["RunRecord"]] = relationship(back_populates="repository", cascade="all, delete-orphan")


class RunRecord(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="issue_prover")
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    verdict: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    claim: Mapped[str] = mapped_column(Text)
    source: Mapped[dict] = mapped_column(JSON, default=dict)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    leased_runner_id: Mapped[str | None] = mapped_column(ForeignKey("runners.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repository: Mapped[RepositoryRecord] = relationship(back_populates="runs")
    events: Mapped[list["RunEventRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="RunEventRecord.sequence")
    artifacts: Mapped[list["ArtifactRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunEventRecord(Base):
    __tablename__ = "run_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    run: Mapped[RunRecord] = relationship(back_populates="events")


class ArtifactRecord(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    uri: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(100), default="application/json")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    redacted: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    run: Mapped[RunRecord] = relationship(back_populates="artifacts")


class GitHubInstallationRecord(Base):
    __tablename__ = "github_installations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    github_installation_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    github_account_login: Mapped[str] = mapped_column(String(200))
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebhookDeliveryRecord(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    delivery_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationEventRecord(Base):
    """External claim/check provenance; records intake without publishing back upstream."""
    __tablename__ = "integration_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str | None] = mapped_column(ForeignKey("repositories.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    external_ref: Mapped[str] = mapped_column(String(500), index=True)
    title: Mapped[str] = mapped_column(Text)
    claim: Mapped[str] = mapped_column(Text, default="")
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="intake", index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True, index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RunnerRecord(Base):
    __tablename__ = "runners"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(30), default="self-hosted")
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    lease_token_hash: Mapped[str] = mapped_column(String(128))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self, url: str = "sqlite:///./reprove.db"):
        options: dict = {"future": True}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if url == "sqlite://":
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False, class_=Session)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)
        # Local installs predate formal migrations. Keep SQLite upgrades additive so
        # existing evidence remains readable when a new ledger column is introduced.
        if self.engine.url.get_backend_name() == "sqlite":
            with self.engine.begin() as connection:
                artifact_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(artifacts)"))}
                if "expires_at" not in artifact_columns:
                    connection.execute(text("ALTER TABLE artifacts ADD COLUMN expires_at DATETIME"))
                run_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(runs)"))}
                if "leased_runner_id" not in run_columns:
                    connection.execute(text("ALTER TABLE runs ADD COLUMN leased_runner_id VARCHAR(36)"))

    def session(self) -> Session:
        return self.sessions()
