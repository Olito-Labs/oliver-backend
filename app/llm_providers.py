import dspy
from typing import Union
from app.config import settings

class LLMProviderManager:
    """Manages different LLM providers for DSPy."""
    
    def __init__(self):
        """Initializes the LLM provider manager."""
        self.current_lm = None
        self.initialize_provider()
    
    def initialize_provider(self) -> None:
        """
        Initialize the current LLM provider based on application settings.
        This method sets up the language model from OpenAI, Anthropic, or Google
        based on the configuration.
        """
        provider = settings.LLM_PROVIDER
        api_key = settings.current_api_key
        model = settings.current_model
        
        if not api_key:
            # A dummy key is used for the fallback, so we only raise an error
            # if a real provider is selected without a key.
            if provider != "fallback":
                raise ValueError(f"API key not provided for {provider}")
        
        try:
            # Select the appropriate DSPy module based on the provider.
            if provider == "openai":
                self.current_lm = dspy.OpenAI(
                    model=model,  # e.g., "gpt-4o"
                    api_key=api_key,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE
                )
            elif provider == "anthropic":
                self.current_lm = dspy.Anthropic(
                    model=model, # e.g., "claude-3-sonnet-20240229"
                    api_key=api_key,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE
                )
            elif provider == "google":
                self.current_lm = dspy.Google(
                    model=model,  # e.g., "gemini-1.5-pro-latest"
                    api_key=api_key,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            # Configure DSPy's global settings to use the selected language model.
            dspy.settings.configure(lm=self.current_lm)
            print(f"Successfully initialized {provider} with model {model}")
            
        except Exception as e:
            print(f"Failed to initialize {provider}: {e}")
            # If initialization fails, fall back to a default setting.
            self._initialize_fallback()
    
    def _initialize_fallback(self) -> None:
        """
        Initializes a fallback LLM provider (OpenAI's GPT-3.5 Turbo)
        in case the primary provider fails. This uses a dummy API key
        and is intended for environments where a real key might not be present.
        """
        print("Initializing fallback LLM provider (gpt-3.5-turbo)...")
        try:
            # Using a widely available and cost-effective model for the fallback.
            self.current_lm = dspy.OpenAI(
                model="gpt-3.5-turbo",
                api_key="dummy-key",  # A dummy key is sufficient for some setups.
                max_tokens=1500,
                temperature=0.7
            )
            dspy.settings.configure(lm=self.current_lm)
            print("Fallback provider initialized.")
        except Exception as e:
            print(f"Could not initialize fallback provider: {e}")
            self.current_lm = None
    
    def switch_provider(self, provider: str, api_key: str = None, model: str = None) -> bool:
        """
        Switch to a different LLM provider and/or model dynamically.

        Args:
            provider (str): The new provider to switch to ("openai", "anthropic", "google").
            api_key (str, optional): The API key for the new provider.
            model (str, optional): The model name for the new provider.

        Returns:
            bool: True if the switch was successful, False otherwise.
        """
        old_provider = settings.LLM_PROVIDER
        old_model = settings.current_model
        
        try:
            print(f"Switching provider to {provider} with model {model or 'default'}...")
            settings.LLM_PROVIDER = provider
            
            # Update the API key and model in the settings.
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
            
            # Re-initialize with the new settings.
            self.initialize_provider()
            return True
            
        except Exception as e:
            print(f"Failed to switch provider to {provider}: {e}")
            # Revert to the old settings if the switch fails.
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
            "max_tokens": self.current_lm.kwargs.get("max_tokens"),
            "temperature": self.current_lm.kwargs.get("temperature")
        }

# It's good practice to have a single, global instance of the manager.
llm_manager = LLMProviderManager()
