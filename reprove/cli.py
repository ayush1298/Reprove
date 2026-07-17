"""Local-first CLI for the hackathon demo and GitHub Action entrypoint."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict
from pathlib import Path

from .bootstrap import detect_bootstrap
from .benchmark import load_manifest, read_results, run_task, write_report, write_results
from .models import ChangeSet
from .reporting import issue_comment
from .workflows import IssueProver, ReproductionProposal, UpgradeProposal, UpgradeVerifier


def _command(value: str) -> list[str]:
    return shlex.split(value)


def _proposal(args: argparse.Namespace) -> ReproductionProposal:
    return ReproductionProposal(args.test or [], _command(args.command) if args.command else [], args.localized or [], args.question or [], args.documented_intent)


def cmd_inspect(args: argparse.Namespace) -> int:
    plan = detect_bootstrap(Path(args.repo))
    print(json.dumps(asdict(plan), indent=2))
    return 0 if plan.supported else 2


def cmd_reproduce(args: argparse.Namespace) -> int:
    prover = IssueProver(Path(args.repo))
    bundle = prover.prove(args.claim, _proposal(args))
    artifact = prover.publish_local_artifacts(bundle, issue_number=args.issue)
    print(issue_comment(bundle))
    print(f"Artifacts: {artifact}")
    return 0 if bundle.verdict.value == "REPRODUCED" else 1


def cmd_verify_fix(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.change).read_text())
    change = ChangeSet(payload["files"], payload.get("description", "Reprove proposed fix"))
    prover = IssueProver(Path(args.repo))
    proposal = _proposal(args)
    bundle = prover.prove(args.claim, proposal)
    bundle = prover.verify_fix(bundle, proposal, change, _command(args.nearby) if args.nearby else None)
    artifact = prover.publish_local_artifacts(bundle, change, args.issue)
    print(issue_comment(bundle))
    print(f"Artifacts: {artifact}")
    return 0 if bundle.verdict.value == "FIX_VERIFIED" else 1


def cmd_upgrade(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.upgrade).read_text())
    proposal = UpgradeProposal(payload["dependency"], payload["old_version"], payload["new_version"], ChangeSet(payload["bump"]["files"], payload["bump"].get("description", "Dependency bump")), payload["canary_tests"], _command(payload["canary_command"]), payload.get("changelog_notes", ""))
    bundle = UpgradeVerifier(Path(args.repo)).verify(proposal, _command(args.nearby) if args.nearby else None)
    target = Path(args.repo) / ".reprove" / "upgrade"
    from .evidence import write_bundle
    write_bundle(bundle, target)
    (target / "issue-comment.md").write_text(issue_comment(bundle))
    print(issue_comment(bundle))
    return 0 if bundle.verdict.value in {"REPRODUCED", "NOT_A_BUG"} else 1


def cmd_benchmark_validate(args: argparse.Namespace) -> int:
    tasks = load_manifest(Path(args.manifest))
    ready = sum(task.status == "ready" for task in tasks)
    print(json.dumps({"tasks": len(tasks), "ready": ready, "candidates": len(tasks) - ready, "read_only": True}, indent=2))
    return 0


def cmd_benchmark_run(args: argparse.Namespace) -> int:
    tasks = load_manifest(Path(args.manifest))
    selected = [task for task in tasks if task.status == "ready" and (args.task in {"all", task.id})]
    if not selected:
        print("No ready benchmark tasks selected. Candidate metadata is intentionally not cloned or executed.", file=sys.stderr)
        return 2
    results = [run_task(task) for task in selected]
    write_results(results, Path(args.output))
    print(json.dumps({"output": args.output, "tasks": len(results), "read_only": True}, indent=2))
    return 0 if all(result.verdict == "VALID" for result in results) else 1


def cmd_benchmark_report(args: argparse.Namespace) -> int:
    results = read_results(Path(args.results))
    write_report(results, Path(args.output))
    print(json.dumps({"report": args.output, "tasks": len(results), "read_only": True}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reprove", description="No fix without a failing test.")
    subs = parser.add_subparsers(dest="subcommand", required=True)
    inspect = subs.add_parser("inspect", help="Detect a supported test environment.")
    inspect.add_argument("repo", nargs="?", default="."); inspect.set_defaults(func=cmd_inspect)
    def evidence_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("--repo", default="."); command.add_argument("--claim", required=True)
        command.add_argument("--test", action="append", help="Native evidence test path (repeatable)")
        command.add_argument("--command", help="Evidence test command")
        command.add_argument("--localized", action="append"); command.add_argument("--question", action="append")
        command.add_argument("--documented-intent", action="store_true", help="Classify a stable non-failure as documented behavior.")
        command.add_argument("--issue", type=int)
    reproduce = subs.add_parser("reproduce", help="Execute evidence tests against a bug claim."); evidence_args(reproduce); reproduce.set_defaults(func=cmd_reproduce)
    verify = subs.add_parser("verify-fix", help="Enforce gates around a proposed source-only fix."); evidence_args(verify); verify.add_argument("--change", required=True); verify.add_argument("--nearby"); verify.set_defaults(func=cmd_verify_fix)
    upgrade = subs.add_parser("upgrade", help="Run old-behavior canaries through a dependency bump."); upgrade.add_argument("--repo", default="."); upgrade.add_argument("--upgrade", required=True); upgrade.add_argument("--nearby"); upgrade.set_defaults(func=cmd_upgrade)
    benchmark = subs.add_parser("benchmark", help="Read-only benchmark validation and execution; never writes to remote repositories.")
    benchmark_subs = benchmark.add_subparsers(dest="benchmark_command", required=True)
    validate = benchmark_subs.add_parser("validate", help="Validate candidate/ready task metadata without cloning.")
    validate.add_argument("manifest"); validate.set_defaults(func=cmd_benchmark_validate)
    run = benchmark_subs.add_parser("run", help="Run only local, pinned ready worktrees in disposable copies.")
    run.add_argument("manifest"); run.add_argument("--task", default="all"); run.add_argument("--output", default="artifacts/evaluation/results.jsonl"); run.set_defaults(func=cmd_benchmark_run)
    report = benchmark_subs.add_parser("report", help="Render a local JSON and Markdown report from result JSONL.")
    report.add_argument("results"); report.add_argument("--output", default="artifacts/evaluation/report.json"); report.set_defaults(func=cmd_benchmark_report)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
