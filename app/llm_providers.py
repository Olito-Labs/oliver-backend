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

    def build_responses_params(
        self, 
        input_data, 
        instructions: str, 
        analysis_type: str = "general",
        output_format: str = "json_object",
        max_tokens: int = 6000,
        tools: list = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Build standardized parameters for OpenAI Responses API calls.
        
        This centralizes all model-specific parameter logic to ensure consistency
        across all API modules (chat, exam, documents, presentations, etc.).
        """
        # Base parameters that work for all models
        base_params = {
            "model": settings.OPENAI_MODEL,
            "input": input_data,
            "instructions": instructions,
            "max_output_tokens": max_tokens,
            "store": True,
            "stream": stream,
            "text": {
                "format": {"type": output_format}
            }
        }
        
        # Add tools if provided
        if tools:
            base_params["tools"] = tools
        
        # GPT-5 model specific parameters
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            reasoning_effort = self._get_reasoning_effort_for_task(analysis_type)
            verbosity = self._get_verbosity_for_task(analysis_type)
            
            base_params["reasoning"] = {"effort": reasoning_effort}
            base_params["text"]["verbosity"] = verbosity
            
            print(f"[DEBUG] Using GPT-5 parameters: reasoning={reasoning_effort}, verbosity={verbosity}")
            
        # o3 model specific parameters (legacy support)
        elif settings.OPENAI_MODEL.startswith("o3"):
            base_params["reasoning"] = {
                "effort": "medium",
                "summary": "detailed"
            }
            print(f"[DEBUG] Using o3 model parameters (legacy)")
            
        else:
            # For other models (GPT-4.1, etc.), include sampling parameters
            base_params["temperature"] = settings.TEMPERATURE
            base_params["reasoning"] = {}
            print(f"[DEBUG] Using standard model parameters (with temperature={settings.TEMPERATURE})")
        
        return base_params
    
    def _get_reasoning_effort_for_task(self, analysis_type: str) -> str:
        """Get optimal reasoning effort based on analysis type for GPT-5."""
        if analysis_type in ["examination", "document", "compliance"]:
            # Complex analysis tasks need thorough reasoning
            return "medium"
        elif analysis_type == "presentation":
            # Presentation generation needs structured thinking
            return "medium"
        elif analysis_type == "validation":
            # Evidence validation needs careful analysis
            return "medium"
        else:
            # General queries can use minimal for faster response
            return "minimal"
    
    def _get_verbosity_for_task(self, analysis_type: str) -> str:
        """Get optimal verbosity for GPT-5 based on task type."""
        if analysis_type in ["examination", "document"]:
            # Document analysis needs detailed output
            return "high"
        elif analysis_type in ["compliance", "presentation", "validation"]:
            # Structured tasks need medium detail
            return "medium"
        else:
            # General queries can be more concise
            return "medium"
    
    def parse_responses_output(self, response, expected_format: str = "json") -> str:
        """
        Standardized parsing of OpenAI Responses API output.
        
        Args:
            response: OpenAI Responses API response object
            expected_format: "json" or "text"
            
        Returns:
            Parsed content as string
        """
        content = ""
        if response.output:
            for item in response.output:
                if hasattr(item, 'content') and item.content:
                    for content_item in item.content:
                        if hasattr(content_item, 'text'):
                            content += content_item.text
        return content

# Global instance
openai_manager = OpenAIManager()
