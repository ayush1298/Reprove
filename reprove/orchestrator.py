"""Job orchestration shared by the API, CLI, hosted workers, and future self-hosted runners."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from .models import Verdict
from .store import RunStore
from .models import ChangeSet
from .workflows import IssueProver, ReproductionProposal, UpgradeProposal, UpgradeVerifier


class LocalJobDispatcher:
    """Development dispatcher. Production workers implement the same submit contract via Redis leases."""

    def __init__(self, store: RunStore, max_workers: int = 2):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="reprove-run")

    def submit_issue(self, run_id: str, repository_path: str, claim: str, tests: list[str], command: list[str], questions: list[str] | None = None) -> None:
        self.executor.submit(self._run_issue, run_id, repository_path, claim, tests, command, questions or [])

    def submit_upgrade(self, run_id: str, repository_path: str, proposal: UpgradeProposal, nearby_command: list[str] | None = None) -> None:
        self.executor.submit(self._run_upgrade, run_id, repository_path, proposal, nearby_command)

    def _run_issue(self, run_id: str, repository_path: str, claim: str, tests: list[str], command: list[str], questions: list[str]) -> None:
        try:
            self.store.transition(run_id, "running", "Worker leased run.")
            self.store.transition(run_id, "bootstrapping", "Inspecting repository environment.")
            root = Path(repository_path).resolve()
            if not root.exists() or not root.is_dir():
                self.store.fail(run_id, "Repository checkout is unavailable.", repository_path)
                return
            self.store.transition(run_id, "generating_evidence", "Executing supplied native evidence proposal.")
            proposal = ReproductionProposal(tests=tests, test_command=command, localized_files=[], questions=questions)
            bundle = IssueProver(root).prove(claim, proposal)
            self.store.transition(run_id, "verifying", "Finalizing deterministic evidence gates.")
            summary = bundle.narrative or bundle.verdict.value
            self.store.transition(run_id, "publishing", "Persisting redacted evidence bundle.")
            self.store.complete(run_id, bundle, summary)
        except Exception as error:  # The API must return a durable, inspectable failure rather than lose a job.
            self.store.fail(run_id, "Run failed unexpectedly.", repr(error))

    def _run_upgrade(self, run_id: str, repository_path: str, proposal: UpgradeProposal, nearby_command: list[str] | None) -> None:
        try:
            self.store.transition(run_id, "running", "Worker leased upgrade verification.")
            self.store.transition(run_id, "bootstrapping", "Preparing old-behavior canary baseline.")
            root = Path(repository_path).resolve()
            if not root.exists() or not root.is_dir():
                self.store.fail(run_id, "Repository checkout is unavailable.", repository_path)
                return
            self.store.transition(run_id, "generating_evidence", "Pinning old dependency behavior with canary tests.")
            bundle = UpgradeVerifier(root).verify(proposal, nearby_command)
            self.store.transition(run_id, "verifying", "Recording canary and regression outcomes.")
            self.store.transition(run_id, "publishing", "Persisting upgrade evidence bundle.")
            self.store.complete(run_id, bundle, bundle.narrative or bundle.verdict.value)
        except Exception as error:
            self.store.fail(run_id, "Upgrade verification failed unexpectedly.", repr(error))
