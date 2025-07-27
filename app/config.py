import os
from typing import Literal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application configuration settings."""
    
    # LLM Provider Selection
    LLM_PROVIDER: Literal["openai", "anthropic", "google"] = os.getenv("LLM_PROVIDER", "openai")
    
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Model Configuration
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-4-sonnet")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")
    
    # General Model Settings
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "2000"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    
    # App Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    @property
    def current_model(self) -> str:
        """Get the current model based on provider."""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_MODEL
        elif self.LLM_PROVIDER == "anthropic":
            return self.ANTHROPIC_MODEL
        elif self.LLM_PROVIDER == "google":
            return self.GOOGLE_MODEL
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")
    
    @property
    def current_api_key(self) -> str:
        """Get the current API key based on provider."""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "anthropic":
            return self.ANTHROPIC_API_KEY
        elif self.LLM_PROVIDER == "google":
            return self.GOOGLE_API_KEY
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")

# Global settings instance
settings = Settings() 