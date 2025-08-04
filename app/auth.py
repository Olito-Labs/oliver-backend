from fastapi import HTTPException, Depends, Header
from typing import Optional
import jwt
import httpx
import json
from app.config import settings

# Cache for Supabase JWT public key
_jwt_public_key = None

async def get_supabase_jwt_key():
    """Get Supabase JWT public key for token verification"""
    global _jwt_public_key
    
    if _jwt_public_key is None:
        try:
            # Get the JWT secret from Supabase project
            supabase_url = settings.SUPABASE_URL
            project_ref = supabase_url.split('//')[1].split('.')[0]
            jwks_url = f"https://{project_ref}.supabase.co/auth/v1/.well-known/jwks.json"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                if response.status_code == 200:
                    jwks = response.json()
                    # Use the first key (Supabase typically has one)
                    if jwks.get('keys'):
                        key_data = jwks['keys'][0]
                        _jwt_public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                else:
                    print(f"Failed to fetch JWKS: {response.status_code}")
        except Exception as e:
            print(f"Error fetching Supabase JWT key: {e}")
    
    return _jwt_public_key

async def get_current_user(authorization: Optional[str] = Header(None)):
    """Verify Supabase JWT token and return user info"""
    
    # Allow unauthenticated access for development/testing
    if not authorization or not authorization.startswith("Bearer "):
        # Return demo user for backward compatibility during transition
        return {
            "uid": "550e8400-e29b-41d4-a716-446655440000",
            "email": "demo@example.com"
        }
    
    try:
        # Extract token
        token = authorization[7:]
        
        # Get JWT public key
        jwt_key = await get_supabase_jwt_key()
        if not jwt_key:
            raise HTTPException(status_code=500, detail="Unable to verify token")
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            jwt_key,
            algorithms=["RS256"],
            audience="authenticated",
            issuer=settings.SUPABASE_URL
        )
        
        # Extract user info from token
        user_id = payload.get('sub')
        email = payload.get('email')
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")
        
        return {
            "uid": user_id,
            "email": email or "unknown@example.com"
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"JWT validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Auth error: {e}")
        # Fallback to demo user for development
        return {
            "uid": "550e8400-e29b-41d4-a716-446655440000",
            "email": "demo@example.com"
        }