"""Execution substrate. Docker command construction keeps untrusted repos isolated in production."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from .models import CommandResult


class Runner:
    def __init__(self, root: Path, timeout_seconds: int = 120):
        self.root = root.resolve()
        self.timeout_seconds = timeout_seconds

    def run(self, command: list[str], timeout_seconds: int | None = None) -> CommandResult:
        """Run with a scrubbed environment. Production uses docker_command() below."""
        started = time.monotonic()
        safe_env = {key: value for key, value in os.environ.items() if not any(secret in key.upper() for secret in ("TOKEN", "SECRET", "PASSWORD", "KEY"))}
        safe_env["NO_PROXY"] = "*"
        safe_env["PYTHONUNBUFFERED"] = "1"
        # Third-party developer-machine pytest plugins are not repository test
        # dependencies and can make an otherwise deterministic run flaky.
        safe_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        try:
            proc = subprocess.run(command, cwd=self.root, text=True, capture_output=True, timeout=timeout_seconds or self.timeout_seconds, env=safe_env, check=False)
            return CommandResult(command, proc.returncode, proc.stdout[-20000:], proc.stderr[-20000:], int((time.monotonic() - started) * 1000))
        except subprocess.TimeoutExpired as error:
            return CommandResult(command, 124, (error.stdout or "")[-20000:] if isinstance(error.stdout, str) else "", (error.stderr or "")[-20000:] if isinstance(error.stderr, str) else "", int((time.monotonic() - started) * 1000), timed_out=True)
        except OSError as error:
            return CommandResult(command, 126, "", str(error), int((time.monotonic() - started) * 1000))

    def build(self, command: list[str]) -> CommandResult:
        """Uniform adapter entry point for a repository's inferred build command."""
        return self.run(command)

    def test(self, selector: list[str]) -> CommandResult:
        """Uniform adapter entry point for native test selectors."""
        return self.run(selector)

    def docker_command(self, image: str, command: list[str]) -> list[str]:
        """The deployment adapter: no network, no secrets, capped resources, read-only source."""
        return [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", "2g", "--cpus", "2", "-v", f"{self.root}:/workspace:ro",
            "-w", "/workspace", image, *command,
        ]


@contextmanager
def isolated_checkout(source: Path):
    """Provide a disposable writable checkout for every proposed source change."""
    with tempfile.TemporaryDirectory(prefix="reprove-") as directory:
        target = Path(directory) / "repository"
        ignored = shutil.ignore_patterns(".git", ".reprove", "__pycache__", ".pytest_cache", ".venv", "node_modules")
        shutil.copytree(source, target, ignore=ignored, symlinks=True)
        yield target
