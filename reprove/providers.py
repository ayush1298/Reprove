"""Provider-neutral structured proposal interface; no model can bypass verification gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .agents import OpenAIProposalClient
from .workflows import ReproductionProposal


@dataclass(slots=True)
class ProviderUsage:
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(slots=True)
class ProviderProposal:
    proposal: ReproductionProposal
    usage: ProviderUsage
    raw_response_id: str | None = None


class ProposalProvider(Protocol):
    name: str

    def reproduce(self, claim: str, code_context: str) -> ProviderProposal: ...


class OpenAIProvider:
    """Managed or BYOK OpenAI implementation behind the shared provider contract."""

    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = OpenAIProposalClient(api_key=api_key, model=model)

    def reproduce(self, claim: str, code_context: str) -> ProviderProposal:
        proposal = self.client.propose(claim, code_context)
        return ProviderProposal(proposal, ProviderUsage(provider=self.name, model=self.client.model))


class StaticProposalProvider:
    """Deterministic provider for local demos, tests, and self-hosted integration validation."""

    name = "static"

    def __init__(self, proposal: ReproductionProposal):
        self.proposal = proposal

    def reproduce(self, claim: str, code_context: str) -> ProviderProposal:
        return ProviderProposal(self.proposal, ProviderUsage(provider=self.name, model="deterministic"))


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, ProposalProvider] = {}

    def register(self, provider: ProposalProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> ProposalProvider:
        if name not in self._providers:
            raise ValueError(f"Proposal provider {name!r} is not configured.")
        return self._providers[name]

    def names(self) -> list[str]:
        return sorted(self._providers)
