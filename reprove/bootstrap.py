"""Repository bootstrap detection with an honest supported-tier boundary."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import BootstrapPlan


def _workflow_commands(root: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    for workflow in (root / ".github" / "workflows").glob("*.y*ml") if (root / ".github" / "workflows").exists() else []:
        for line in workflow.read_text(errors="ignore").splitlines():
            match = re.match(r"\s*run:\s*(.+)$", line)
            if match:
                commands.append(match.group(1).strip().split())
    return commands


def detect_bootstrap(root: Path) -> BootstrapPlan:
    """Priority: repo CI, devcontainer, then conventions. Never pretend unsupported is broken."""
    ci_commands = _workflow_commands(root)
    if ci_commands:
        test = next((cmd for cmd in ci_commands if any(x in cmd for x in ("pytest", "test", "vitest", "jest"))), None)
        install = next((cmd for cmd in ci_commands if any(x in cmd for x in ("install", "sync"))), None)
        if test:
            ecosystem = "python" if "pytest" in test else "node"
            return BootstrapPlan(ecosystem, install, test, "github-actions", True)
    if (root / ".devcontainer" / "devcontainer.json").exists() or (root / "devcontainer.json").exists():
        return BootstrapPlan(None, None, None, "devcontainer", False, "Devcontainer detected; run through Docker adapter.")
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "requirements.txt").exists():
        install = ["python", "-m", "pip", "install", "-e", ".[dev]"] if (root / "pyproject.toml").exists() else ["python", "-m", "pip", "install", "-r", "requirements.txt"]
        return BootstrapPlan("python", install, ["python", "-m", "pytest"], "python-convention", True)
    package = root / "package.json"
    if package.exists():
        try:
            manager = "pnpm" if (root / "pnpm-lock.yaml").exists() else "npm"
            scripts = json.loads(package.read_text()).get("scripts", {})
            if "test" in scripts:
                return BootstrapPlan("node", [manager, "install", "--frozen-lockfile"] if manager == "pnpm" else [manager, "ci"], [manager, "test", "--", "--runInBand"], "node-convention", True)
        except json.JSONDecodeError:
            pass
    return BootstrapPlan(None, None, None, "none", False, "No supported Python or Node test configuration was found.")

