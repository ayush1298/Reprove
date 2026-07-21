"""Externalized upstream regression test for pytest-dev/pytest#11706.

This is intentionally stored outside the cloned pytest worktree. It is the
accepted upstream test scenario used by the public issue-replay pilot.
"""

import pytest


def test_teardown_session_failed(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module")
        def baz():
            yield
            pytest.fail("This is a failing teardown")

        def test_foo(baz):
            pytest.fail("This is a failing test")

        def test_bar():
            pass
        """
    )
    result = pytester.runpytest("--maxfail=1")
    result.assert_outcomes(failed=1, errors=1)
