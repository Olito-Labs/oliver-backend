import dspy
from typing import Union
from app.config import settings

class LLMProviderManager:
    """Manages different LLM providers for DSPy using the unified dspy.LM approach."""
    
    def __init__(self):
        """Initializes the LLM provider manager."""
        self.current_lm = None
        self.initialize_provider()
    
    def initialize_provider(self) -> None:
        """
        Initialize the current LLM provider based on application settings.
        Uses the unified dspy.LM class with LiteLLM provider strings.
        """
        provider = settings.LLM_PROVIDER
        api_key = settings.current_api_key
        model = settings.current_model
        
        if not api_key:
            if provider != "fallback":
                raise ValueError(f"API key not provided for {provider}")
        
        try:
            # Use the unified dspy.LM class with LiteLLM provider format
            if provider == "openai":
                model_string = f"openai/{model}"
            elif provider == "anthropic":
                model_string = f"anthropic/{model}"
            elif provider == "google":
                model_string = f"gemini/{model}"
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            # Create the unified LM instance (streamify handles streaming)
            self.current_lm = dspy.LM(
                model=model_string,
                api_key=api_key,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
                # Note: DSPy streamify() handles streaming, not the LM directly
            )
            
            # Configure DSPy's global settings
            dspy.settings.configure(lm=self.current_lm)
            print(f"Successfully initialized {provider} with model {model} using unified dspy.LM")
            
        except Exception as e:
            print(f"Failed to initialize {provider}: {e}")
            self._initialize_fallback()
    
    def _initialize_fallback(self) -> None:
        """
        Initializes a fallback LLM provider using the unified dspy.LM approach.
        """
        print("Initializing fallback LLM provider (gpt-3.5-turbo)...")
        try:
            self.current_lm = dspy.LM(
                model="openai/gpt-3.5-turbo",
                api_key="dummy-key",
                max_tokens=1500,
                temperature=0.7
                # Note: DSPy streamify() handles streaming, not the LM directly
            )
            dspy.settings.configure(lm=self.current_lm)
            print("Fallback provider initialized with unified dspy.LM")
        except Exception as e:
            print(f"Could not initialize fallback provider: {e}")
            self.current_lm = None
    
    def switch_provider(self, provider: str, api_key: str = None, model: str = None) -> bool:
        """
        Switch to a different LLM provider using the unified dspy.LM approach.
        """
        old_provider = settings.LLM_PROVIDER
        old_model = settings.current_model
        
        try:
            print(f"Switching provider to {provider} with model {model or 'default'}...")
            settings.LLM_PROVIDER = provider
            
            # Update API key and model settings
            if api_key:
                if provider == "openai":
                    settings.OPENAI_API_KEY = api_key
                elif provider == "anthropic":
                    settings.ANTHROPIC_API_KEY = api_key
                elif provider == "google":
                    settings.GOOGLE_API_KEY = api_key

            if model:
                if provider == "openai":
                    settings.OPENAI_MODEL = model
                elif provider == "anthropic":
                    settings.ANTHROPIC_MODEL = model
                elif provider == "google":
                    settings.GOOGLE_MODEL = model
            
            # Re-initialize with new settings
            self.initialize_provider()
            return True
            
        except Exception as e:
            print(f"Failed to switch provider to {provider}: {e}")
            # Revert settings on failure
            settings.LLM_PROVIDER = old_provider
            if provider == "openai":
                settings.OPENAI_MODEL = old_model
            elif provider == "anthropic":
                settings.ANTHROPIC_MODEL = old_model
            elif provider == "google":
                settings.GOOGLE_MODEL = old_model
                
            self.initialize_provider()
            return False
    
    def get_current_provider_info(self) -> dict:
        """Get information about the current LLM provider and configuration."""
        if not self.current_lm:
            return {"provider": "None", "model": "N/A"}
            
        return {
            "provider": settings.LLM_PROVIDER,
            "model": settings.current_model,
            "max_tokens": settings.MAX_TOKENS,
            "temperature": settings.TEMPERATURE
        }

# Global instance
llm_manager = LLMProviderManager()
