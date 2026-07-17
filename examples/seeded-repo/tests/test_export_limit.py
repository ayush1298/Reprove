from limit import allows_export


def test_allows_an_export_at_the_documented_limit():
    assert allows_export(100)
