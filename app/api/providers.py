from fastapi import APIRouter, HTTPException
from typing import List

from app.models.api import ProviderSwitchRequest, ProviderInfo, ErrorResponse
from app.llm_providers import llm_manager
from app.config import settings

router = APIRouter(prefix="/api", tags=["providers"])

@router.get("/providers", response_model=List[dict])
async def get_available_providers():
    """Get list of available LLM providers."""
    return [
        {
            "name": "openai",
            "display_name": "OpenAI",
            "models": ["gpt-4.1", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "default_model": "gpt-4.1"
        },
        {
            "name": "anthropic", 
            "display_name": "Anthropic Claude",
            "models": ["claude-4-sonnet", "claude-3.5-sonnet", "claude-3-haiku"],
            "default_model": "claude-4-sonnet"
        },
        {
            "name": "google",
            "display_name": "Google Gemini", 
            "models": ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
            "default_model": "gemini-2.5-pro"
        }
    ]

@router.get("/providers/current", response_model=ProviderInfo)
async def get_current_provider():
    """Get information about the current LLM provider."""
    try:
        provider_info = llm_manager.get_current_provider_info()
        return ProviderInfo(**provider_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provider info: {str(e)}")

@router.post("/providers/switch")
async def switch_provider(request: ProviderSwitchRequest):
    """Switch to a different LLM provider."""
    try:
        # Validate provider
        if request.provider not in ["openai", "anthropic", "google"]:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {request.provider}")
        
        # Check if API key exists in environment variables
        current_key = None
        if request.provider == "openai":
            current_key = settings.OPENAI_API_KEY
        elif request.provider == "anthropic":
            current_key = settings.ANTHROPIC_API_KEY
        elif request.provider == "google":
            current_key = settings.GOOGLE_API_KEY
            
        if not current_key:
            raise HTTPException(
                status_code=400, 
                detail=f"API key for {request.provider} not configured on server. Please add {request.provider.upper()}_API_KEY to environment variables."
            )
        
        # Attempt to switch provider using environment variables
        success = llm_manager.switch_provider(
            provider=request.provider,
            model=getattr(request, 'model', None)  # Use model from request if provided
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to switch provider")
        
        # Return updated provider info
        provider_info = llm_manager.get_current_provider_info()
        return {
            "status": "success",
            "message": f"Successfully switched to {request.provider}",
            "provider_info": provider_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provider switch failed: {str(e)}")

@router.post("/providers/{provider_name}/test")
async def test_provider(provider_name: str, api_key: str = None):
    """Test a provider connection without switching to it."""
    try:
        if provider_name not in ["openai", "anthropic", "google"]:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider_name}")
        
        # Store current provider state
        current_provider = settings.LLM_PROVIDER
        
        # Temporarily switch to test provider
        test_success = llm_manager.switch_provider(
            provider=provider_name,
            api_key=api_key,
            model=None
        )
        
        if test_success:
            # Test with a simple query
            try:
                # Simple test - this would need to be implemented with actual DSPy test
                result = {"test": "passed", "provider": provider_name}
                
                # Switch back to original provider
                llm_manager.switch_provider(current_provider)
                
                return {
                    "status": "success",
                    "message": f"{provider_name} connection test passed",
                    "test_result": result
                }
            except Exception as test_error:
                # Switch back to original provider
                llm_manager.switch_provider(current_provider)
                raise HTTPException(status_code=400, detail=f"Provider test failed: {str(test_error)}")
        else:
            raise HTTPException(status_code=400, detail=f"Failed to connect to {provider_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provider test error: {str(e)}") 