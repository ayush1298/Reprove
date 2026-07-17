from reprove.models import ChangeSet, Gate
from reprove.policy import Policy
from reprove.safety import enforce_fix_boundary, lint_unified_diff


def test_fix_loop_cannot_write_a_test_file():
    result = enforce_fix_boundary(ChangeSet({"tests/test_login.py": "assert True\n"}, "cheat"), Policy())
    assert result.gate is Gate.ANTI_CHEAT
    assert not result.passed
    assert "test files" in result.summary


def test_skip_marker_is_rejected_even_outside_tests():
    result = enforce_fix_boundary(ChangeSet({"app.py": "pytest.skip('hide failure')\n"}, "cheat"), Policy())
    assert not result.passed
    assert "assertion weakening" in result.summary


def test_production_change_is_permitted():
    result = enforce_fix_boundary(ChangeSet({"app.py": "return value >= 10\n"}, "valid"), Policy())
    assert result.passed


def test_raw_diff_assertion_removal_is_rejected():
    result = lint_unified_diff("--- a/tests/test_app.py\n+++ b/tests/test_app.py\n-assert response.status_code == 200\n")
    assert not result.passed
