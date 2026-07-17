from reprove.github_events import normalize_trigger


def test_label_trigger_normalizes_issue():
    trigger = normalize_trigger("issues", {"action": "labeled", "label": {"name": "reprove"}, "repository": {"full_name": "acme/demo"}, "issue": {"number": 4, "title": "It fails"}, "installation": {"id": 9}})
    assert trigger and trigger.kind == "issue_prover"
    assert trigger.repository == "acme/demo"


def test_irrelevant_webhook_is_ignored():
    assert normalize_trigger("push", {"repository": {"full_name": "acme/demo"}}) is None
