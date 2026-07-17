"""Queue worker entry point for hosted deployments."""

from __future__ import annotations

import os
from pathlib import Path

from .database import Database
from .jobs import RedisJobDispatcher
from .models import ChangeSet
from .orchestrator import LocalJobDispatcher
from .store import RunStore
from .workflows import UpgradeProposal


def process_one(dispatcher: RedisJobDispatcher, executor: LocalJobDispatcher, timeout_seconds: int = 5) -> bool:
    job = dispatcher.dequeue(timeout_seconds)
    if not job:
        return False
    if job.kind == "issue_prover":
        executor._run_issue(job.run_id, **job.payload)
    elif job.kind == "upgrade_verifier":
        data = job.payload["proposal"]
        proposal = UpgradeProposal(data["dependency"], data["old_version"], data["new_version"], ChangeSet(data["files"], f"Upgrade {data['dependency']}"), data["canary_tests"], data["canary_command"], data["changelog_notes"])
        executor._run_upgrade(job.run_id, job.payload["repository_path"], proposal, job.payload.get("nearby_command"))
    else:
        executor.store.fail(job.run_id, "Unknown worker job kind.", job.kind)
    return True


def main() -> None:
    database = Database(os.environ.get("REPROVE_DATABASE_URL", "sqlite:///./reprove.db")); database.create_all()
    store = RunStore(database, Path(os.environ.get("REPROVE_ARTIFACT_ROOT", ".reprove-service/artifacts")))
    dispatcher = RedisJobDispatcher(os.environ["REPROVE_REDIS_URL"])
    executor = LocalJobDispatcher(store, max_workers=1)
    while True:
        process_one(dispatcher, executor, 5)
