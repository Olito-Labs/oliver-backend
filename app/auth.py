from fastapi import HTTPException, Depends, Header
from typing import Optional
import uuid

# Simplified auth for now - can be enhanced later
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Simple auth - returns mock user for now"""
    # For now, return a mock user - we'll enhance this later
    # This allows the API to work immediately
    if authorization and authorization.startswith("Bearer "):
        # Extract token (we'll validate this properly later)
        token = authorization[7:]
        return {
            "uid": "550e8400-e29b-41d4-a716-446655440000",  # Valid UUID for mock user
            "email": "demo@example.com"
        }
    else:
        # For immediate testing, allow unauthenticated access
        return {
            "uid": "550e8400-e29b-41d4-a716-446655440000",  # Valid UUID for mock user
            "email": "demo@example.com"
        }