from fastapi import APIRouter
from datetime import datetime

from app.models.api import HealthResponse, ProviderInfo
from app.llm_providers import llm_manager

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    provider_info = llm_manager.get_current_provider_info()
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        provider_info=ProviderInfo(**provider_info),
        version="1.0.0"
    )

@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Oliver Backend API", "version": "1.0.0"} 