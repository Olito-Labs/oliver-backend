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
        return {
            "provider": "openai",
            "model": settings.OPENAI_MODEL,
            "max_tokens": settings.MAX_TOKENS,
            "temperature": settings.TEMPERATURE
        }
    
    def get_web_search_tool_name(self) -> str:
        """Get correct web search tool name based on model."""
        # Critical fix: Use correct tool name based on model type
        return "web_search_preview" if settings.OPENAI_MODEL.endswith("-preview") else "web_search"

# Global instance
openai_manager = OpenAIManager()
