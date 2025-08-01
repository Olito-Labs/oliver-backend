from openai import OpenAI
from app.config import settings
from typing import Dict, Any

class OpenAIManager:
    """Simplified OpenAI client manager for Responses API."""
    
    def __init__(self):
        self.client = None
        self.initialize_client()
    
    def initialize_client(self) -> None:
        """Initialize OpenAI client."""
        try:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required")
                
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            print(f"OpenAI client initialized with model: {settings.OPENAI_MODEL}")
        except Exception as e:
            print(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    def get_client(self) -> OpenAI:
        """Get the OpenAI client instance."""
        if not self.client:
            self.initialize_client()
        return self.client
    
    def get_current_provider_info(self) -> Dict[str, Any]:
        """Get current provider information."""
        info = {
            "provider": "openai",
            "model": settings.OPENAI_MODEL,
            "max_tokens": settings.MAX_TOKENS
        }
        
        # Only include temperature for models that support it (not o3)
        if not settings.OPENAI_MODEL.startswith("o3"):
            info["temperature"] = settings.TEMPERATURE
        else:
            info["reasoning_effort"] = "medium"
            info["reasoning_summary"] = "detailed"
            info["note"] = "o3 models use reasoning effort instead of temperature"
        
        return info
    
    def get_web_search_tool_name(self) -> str:
        """Get correct web search tool name based on model."""
        # For o3 and GPT-4.1, always use web_search_preview as per OpenAI documentation
        if settings.OPENAI_MODEL.startswith("o3") or settings.OPENAI_MODEL.startswith("gpt-4.1"):
            return "web_search_preview"
        # For other models, check if it's a preview variant
        return "web_search_preview" if settings.OPENAI_MODEL.endswith("-preview") else "web_search"

# Global instance
openai_manager = OpenAIManager()
