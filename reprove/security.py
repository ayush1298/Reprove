"""Small deployment guard for control-plane mutations.

Local development is intentionally frictionless. Deployments set REPROVE_API_TOKEN
until GitHub OAuth/session middleware is configured by the hosting environment.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_control_plane_access(authorization: str = Header(default="")) -> None:
    configured = os.environ.get("REPROVE_API_TOKEN")
    if not configured:
        return
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=401, detail="Control-plane authentication required.")
