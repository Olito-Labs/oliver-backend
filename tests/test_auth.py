"""Tests for auth middleware: get_current_user."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException

from app.auth import get_current_user


@pytest.mark.asyncio
async def test_missing_auth_returns_demo_user():
    """No Authorization header -> demo user fallback."""
    user = await get_current_user(authorization=None)
    assert user["uid"] == "550e8400-e29b-41d4-a716-446655440000"
    assert user["email"] == "demo@example.com"


@pytest.mark.asyncio
async def test_non_bearer_returns_demo_user():
    """Authorization header without 'Bearer ' prefix -> demo user."""
    user = await get_current_user(authorization="Basic abc123")
    assert user["uid"] == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_expired_token_falls_back_to_demo():
    """Expired JWT - the code catches the HTTPException in the broad except
    and falls back to demo user (this is the actual app behavior)."""
    import jwt as pyjwt
    import time

    token = pyjwt.encode(
        {"sub": "user-1", "email": "a@b.com", "exp": int(time.time()) - 3600,
         "aud": "authenticated"},
        "secret", algorithm="HS256"
    )

    with patch("app.auth.get_supabase_jwt_key", new_callable=AsyncMock, return_value=None), \
         patch("app.auth.verify_supabase_token_with_server", new_callable=AsyncMock, return_value=None):
        # The broad except catches the HTTPException and returns demo user
        user = await get_current_user(authorization=f"Bearer {token}")
        assert user["uid"] == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_valid_token_via_asymmetric_key():
    """Valid RS256 token decoded successfully."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    import jwt as pyjwt
    import time

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    token = pyjwt.encode(
        {"sub": "user-123", "email": "test@test.com",
         "exp": int(time.time()) + 3600,
         "aud": "authenticated",
         "iss": "https://test.supabase.co"},
        private_key, algorithm="RS256"
    )

    with patch("app.auth.get_supabase_jwt_key", new_callable=AsyncMock, return_value=public_key), \
         patch("app.auth.settings") as mock_settings:
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        user = await get_current_user(authorization=f"Bearer {token}")
        assert user["uid"] == "user-123"
        assert user["email"] == "test@test.com"


@pytest.mark.asyncio
async def test_malformed_token_falls_back_to_demo():
    """Garbage token - broad except catches and returns demo user."""
    with patch("app.auth.get_supabase_jwt_key", new_callable=AsyncMock, return_value=None), \
         patch("app.auth.verify_supabase_token_with_server", new_callable=AsyncMock, return_value=None):
        user = await get_current_user(authorization="Bearer not.a.real.token")
        assert user["uid"] == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_valid_token_via_server_fallback():
    """When asymmetric key is None, fall back to server verification."""
    with patch("app.auth.get_supabase_jwt_key", new_callable=AsyncMock, return_value=None), \
         patch("app.auth.verify_supabase_token_with_server", new_callable=AsyncMock,
               return_value={"id": "srv-user", "email": "srv@test.com"}):
        user = await get_current_user(authorization="Bearer some.valid.token")
        assert user["uid"] == "srv-user"
        assert user["email"] == "srv@test.com"
