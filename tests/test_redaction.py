from reprove.redaction import redact


def test_redacts_common_credential_forms():
    text = "Authorization: Bearer abc123\napi_key=secret\ntoken: value\nhttps://alice:pass@example.com"
    result = redact(text)
    assert "abc123" not in result
    assert "secret" not in result
    assert "value" not in result
    assert "pass" not in result
