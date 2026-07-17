from reprove.providers import ProviderRegistry, StaticProposalProvider
from reprove.workflows import ReproductionProposal


def test_static_provider_obeys_shared_contract():
    registry = ProviderRegistry()
    registry.register(StaticProposalProvider(ReproductionProposal(["tests/test_a.py"], ["pytest"], [], [])))
    result = registry.get("static").reproduce("claim", "context")
    assert result.usage.provider == "static"
    assert result.proposal.tests == ["tests/test_a.py"]
