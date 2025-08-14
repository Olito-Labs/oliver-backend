from openai import OpenAI
from app.config import settings
from typing import Dict, Any

class OpenAIManager:
    """OpenAI client manager for Responses API with GPT-5 support."""
    
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
        
        # GPT-5 specific features
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            info["reasoning_effort"] = "medium"  # Default for GPT-5
            info["verbosity"] = "medium"  # Default verbosity
            info["supports_minimal_reasoning"] = True
            info["supports_custom_tools"] = True
            info["note"] = "GPT-5 with reasoning effort and verbosity control"
        # o3 model features (legacy support)
        elif settings.OPENAI_MODEL.startswith("o3"):
            info["reasoning_effort"] = "medium"
            info["reasoning_summary"] = "detailed"
            info["note"] = "o3 models use reasoning effort instead of temperature"
        # Traditional models with temperature
        else:
            info["temperature"] = settings.TEMPERATURE
            info["note"] = "Traditional model with temperature control"
        
        return info
    
    def get_web_search_tool_name(self) -> str:
        """Get correct web search tool name based on model."""
        # For GPT-5, o3, and GPT-4.1, always use web_search_preview
        if (settings.OPENAI_MODEL.startswith("gpt-5") or 
            settings.OPENAI_MODEL.startswith("o3") or 
            settings.OPENAI_MODEL.startswith("gpt-4.1")):
            return "web_search_preview"
        # For other models, check if it's a preview variant
        return "web_search_preview" if settings.OPENAI_MODEL.endswith("-preview") else "web_search"
    
    def get_default_reasoning_effort(self) -> str:
        """Get default reasoning effort based on model and use case."""
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            # For Oliver's compliance use cases, medium provides good balance
            return "medium"
        elif settings.OPENAI_MODEL.startswith("o3"):
            return "medium"
        else:
            # Non-reasoning models don't use this parameter
            return None
    
    def get_default_verbosity(self) -> str:
        """Get default verbosity for GPT-5."""
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            # Medium verbosity for compliance explanations
            return "medium"
        else:
            return None

# Global instance
openai_manager = OpenAIManager()
