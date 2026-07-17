"""Hosted/self-hosted runner capability and signed-lease primitives."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass


@dataclass(slots=True)
class RunnerLease:
    runner_id: str
    token: str
    expires_in_seconds: int = 300


def new_lease(runner_id: str) -> RunnerLease:
    return RunnerLease(runner_id=runner_id, token=secrets.token_urlsafe(32))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
