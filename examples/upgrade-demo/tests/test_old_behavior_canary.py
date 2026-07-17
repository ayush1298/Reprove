from compat import parse_empty_response


def test_empty_response_remains_an_object():
    assert parse_empty_response() == {}
