from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.models.api import HealthResponse, ProviderInfo
from app.llm_providers import openai_manager

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with OpenAI client validation."""
    try:
        # Get provider info from the new OpenAI manager
        provider_info = openai_manager.get_current_provider_info()
        
        # Test OpenAI client connectivity
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=503, detail="OpenAI client not initialized")
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            provider_info=ProviderInfo(**provider_info),
            version="1.0.0"
        )
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Oliver Backend API - OpenAI Migration", "version": "1.0.0"} 