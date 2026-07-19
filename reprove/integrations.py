"""Inbound integration normalization with no provider-side write capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Provider = Literal["sentry", "linear", "jira", "github"]


@dataclass(frozen=True, slots=True)
class NormalizedSignal:
    provider: Provider
    external_ref: str
    title: str
    claim: str
    external_url: str | None = None
    fingerprint: str | None = None
    severity: str | None = None


def normalize_signal(provider: Provider, payload: dict[str, Any]) -> NormalizedSignal:
    """Convert common webhook shapes to a safe, provider-neutral evidence claim."""
    if provider == "sentry":
        issue = payload.get("data", {}).get("issue", payload.get("issue", payload))
        ref = str(issue.get("id") or issue.get("shortId") or payload.get("id") or "unknown")
        title = issue.get("title") or issue.get("culprit") or "Sentry incident"
        return NormalizedSignal(provider, ref, title, issue.get("metadata", {}).get("value") or title, issue.get("permalink") or issue.get("web_url"), issue.get("fingerprint") or issue.get("shortId"), issue.get("level"))
    if provider == "linear":
        issue = payload.get("data", payload)
        ref = str(issue.get("identifier") or issue.get("id") or "unknown")
        title = issue.get("title") or "Linear issue"
        return NormalizedSignal(provider, ref, title, issue.get("description") or title, issue.get("url"), issue.get("id"), issue.get("priorityLabel") or str(issue.get("priority") or ""))
    if provider == "jira":
        issue = payload.get("issue", payload)
        fields = issue.get("fields", {})
        ref = str(issue.get("key") or issue.get("id") or "unknown")
        title = fields.get("summary") or "Jira issue"
        base = payload.get("baseUrl") or ""
        return NormalizedSignal(provider, ref, title, fields.get("description") or title, f"{base}/browse/{ref}" if base and ref != "unknown" else None, ref, fields.get("priority", {}).get("name"))
    issue = payload.get("issue", payload)
    ref = str(issue.get("number") or issue.get("id") or "unknown")
    title = issue.get("title") or "GitHub issue"
    return NormalizedSignal(provider, ref, title, issue.get("body") or title, issue.get("html_url"), str(issue.get("number") or ""), None)


def as_dict(signal: NormalizedSignal) -> dict[str, str | None]:
    return {"provider": signal.provider, "external_ref": signal.external_ref, "title": signal.title, "claim": signal.claim, "external_url": signal.external_url, "fingerprint": signal.fingerprint, "severity": signal.severity}
