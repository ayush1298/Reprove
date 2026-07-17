def allows_export(record_count: int) -> bool:
    """Bug: accounts exactly at the limit should be allowed."""
    return record_count > 100
