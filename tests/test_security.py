import pytest
from fastapi import HTTPException

from reprove.security import require_control_plane_access


def test_control_plane_token_is_optional_for_local_development(monkeypatch):
    monkeypatch.delenv("REPROVE_API_TOKEN", raising=False)
    require_control_plane_access("")


def test_control_plane_token_is_checked_when_configured(monkeypatch):
    monkeypatch.setenv("REPROVE_API_TOKEN", "correct")
    with pytest.raises(HTTPException):
        require_control_plane_access("Bearer wrong")
    require_control_plane_access("Bearer correct")
