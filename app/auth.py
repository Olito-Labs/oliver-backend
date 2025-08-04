from fastapi import HTTPException, Depends, Header
from typing import Optional
import uuid

# Use a consistent UUID for demo user to maintain data consistency
DEMO_USER_UUID = "12345678-1234-5678-9abc-123456789abc"

# Simplified auth for now - can be enhanced later
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Simple auth - returns mock user for now"""
    # For now, return a mock user - we'll enhance this later
    # This allows the API to work immediately
    if authorization and authorization.startswith("Bearer "):
        # Extract token (we'll validate this properly later)
        token = authorization[7:]
        return {
            "uid": DEMO_USER_UUID,  # Consistent UUID for demo user
            "email": "demo@example.com"
        }
    else:
        # For immediate testing, allow unauthenticated access
        return {
            "uid": DEMO_USER_UUID,  # Consistent UUID for demo user
            "email": "demo@example.com"
        }