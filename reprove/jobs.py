"""Redis queue adapter sharing the same payload contract as the local dispatcher."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from redis import Redis


@dataclass(slots=True)
class Job:
    run_id: str
    kind: str
    payload: dict[str, Any]

    def encode(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def decode(cls, value: str | bytes) -> "Job":
        if isinstance(value, bytes):
            value = value.decode()
        return cls(**json.loads(value))


class RedisJobDispatcher:
    queue_name = "reprove:jobs"

    def __init__(self, url: str, client: Redis | None = None):
        self.client = client or Redis.from_url(url, decode_responses=True)

    def enqueue(self, job: Job) -> None:
        self.client.lpush(self.queue_name, job.encode())

    def dequeue(self, timeout_seconds: int = 5) -> Job | None:
        item = self.client.brpop(self.queue_name, timeout=timeout_seconds)
        return Job.decode(item[1]) if item else None

    def submit_issue(self, run_id: str, repository_path: str, claim: str, tests: list[str], command: list[str], questions: list[str] | None = None) -> None:
        self.enqueue(Job(run_id, "issue_prover", {"repository_path": repository_path, "claim": claim, "tests": tests, "command": command, "questions": questions or []}))

    def submit_upgrade(self, run_id: str, repository_path: str, proposal, nearby_command: list[str] | None = None) -> None:
        self.enqueue(Job(run_id, "upgrade_verifier", {"repository_path": repository_path, "proposal": {"dependency": proposal.dependency, "old_version": proposal.old_version, "new_version": proposal.new_version, "files": proposal.bump.files, "canary_tests": proposal.canary_tests, "canary_command": proposal.canary_command, "changelog_notes": proposal.changelog_notes}, "nearby_command": nearby_command}))
