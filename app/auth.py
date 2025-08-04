from fastapi import HTTPException, Depends, Header
from typing import Optional
import uuid
from app.supabase_client import supabase

# Use a consistent UUID for demo user to maintain data consistency
DEMO_USER_UUID = "12345678-1234-5678-9abc-123456789abc"

async def ensure_demo_user_exists():
    """Ensure the demo user exists in auth.users for testing purposes"""
    try:
        # Use admin API to create user if not exists
        user_response = supabase.auth.admin.create_user({
            "user_id": DEMO_USER_UUID,
            "email": "demo@example.com",
            "email_confirm": True,
            "user_metadata": {
                "name": "Demo User"
            }
        })
        print(f"Demo user created or already exists")
    except Exception as e:
        # User might already exist, which is fine
        print(f"Demo user handling: {e}")

# Simplified auth for now - can be enhanced later
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Simple auth - returns mock user for now"""
    # Ensure demo user exists on each request (for testing)
    await ensure_demo_user_exists()
    
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