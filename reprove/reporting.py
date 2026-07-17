"""Human-readable evidence artifacts suitable for issue comments and draft PR descriptions."""

from __future__ import annotations

from .models import EvidenceBundle, Gate


def issue_comment(bundle: EvidenceBundle) -> str:
    lines = [f"## Reprove verdict: `{bundle.verdict.value}`", "", bundle.narrative or "Execution-backed triage completed.", "", "### Evidence gates", ""]
    for gate in bundle.gates:
        mark = "✅" if gate.passed else "⚠️"
        lines.append(f"- {mark} **{gate.gate.value.replace('_', ' ')}** — {gate.summary}")
    if bundle.tests:
        lines.extend(["", "### Evidence tests", *[f"- `{test}`" for test in bundle.tests]])
    if bundle.proposed_questions:
        lines.extend(["", "### Information needed", *[f"- {question}" for question in bundle.proposed_questions]])
    lines.extend(["", f"**Objective confidence:** {bundle.confidence}/100", "", "_Reprove never reports an environment failure as a bug reproduction._"])
    return "\n".join(lines) + "\n"


def pull_request_body(bundle: EvidenceBundle, change_summary: str) -> str:
    status = "Draft" if not all(gate.passed for gate in bundle.gates if gate.gate in (Gate.MUTATION, Gate.BLAST_RADIUS)) else "Ready for review"
    return "\n".join([
        f"# {status}: Reprove evidence bundle",
        "", "## Claim", bundle.claim,
        "", "## Root cause", bundle.narrative or "See execution artifacts.",
        "", "## Fix", change_summary,
        "", "## Execution evidence", *[f"- {'✅' if gate.passed else '⚠️'} {gate.gate.value}: {gate.summary}" for gate in bundle.gates],
        "", f"## Objective confidence\n{bundle.confidence}/100",
        "", "The fixing agent was mechanically prevented from changing evidence tests.",
    ]) + "\n"
