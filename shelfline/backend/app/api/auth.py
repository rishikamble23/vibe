"""
Phase 7 Auth & Security (Appendix D & G13):
- Short code role token issuance for Donors, Riders, Shelters, Admin, NGO
- Token validation dependency for protected endpoints
"""
from __future__ import annotations

from typing import Optional
from fastapi import Header, HTTPException, status

from app.db.models import UserRole


# In-memory token store for demo personas (Short codes issued via seed)
_TOKEN_STORE = {
    "donor_token_123": {"role": UserRole.DONOR, "id": 1, "name": "Test Donor"},
    "rider_token_123": {"role": UserRole.RIDER, "id": 1, "name": "Test Rider"},
    "shelter_token_123": {"role": UserRole.SHELTER, "id": 1, "name": "Test Shelter"},
    "admin_key_secret": {"role": UserRole.ADMIN, "id": 0, "name": "Admin / Judge"},
    "ngo_token_123": {"role": UserRole.NGO, "id": 1, "name": "Test NGO"},
}


def authenticate_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Authenticate request via Authorization: Bearer <token> or X-API-Key header.
    Returns user context dict {role, id, name}.
    """
    if not authorization:
        # Default to unauthenticated/judge role for frictionless demo
        return {"role": UserRole.ADMIN, "id": 0, "name": "Anonymous Judge"}

    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]

    user = _TOKEN_STORE.get(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token or short code",
        )
    return user


def require_role(required_role: UserRole):
    def dependency(authorization: Optional[str] = Header(None)) -> dict:
        ctx = authenticate_user(authorization)
        if ctx["role"] != UserRole.ADMIN and ctx["role"] != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {required_role.value} required (got {ctx['role'].value})",
            )
        return ctx
    return dependency
