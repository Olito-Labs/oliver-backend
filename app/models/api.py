from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

class ChatMessage(BaseModel):
    """Model for chat messages."""
    id: str
    content: str
    sender: Literal["user", "assistant"]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    """Request model for chat endpoints."""
    messages: List[ChatMessage]
    study_id: Optional[str] = None
    analysis_type: Literal["general", "compliance", "document"] = "general"
    context: Optional[str] = ""
    stream: bool = True

class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    message: ChatMessage
    artifacts: Optional[List[Dict[str, Any]]] = []
    reasoning: Optional[str] = ""
    analysis_type: Optional[str] = ""

class StreamChunk(BaseModel):
    """Model for streaming response chunks."""
    type: Literal["content", "artifacts", "done", "error"]
    content: str
    done: bool = False
    metadata: Optional[Dict[str, Any]] = None

class ProviderSwitchRequest(BaseModel):
    """Request to switch LLM provider."""
    provider: Literal["openai", "anthropic", "google"]
    api_key: Optional[str] = None

class ProviderInfo(BaseModel):
    """Information about current LLM provider."""
    provider: str
    model: str
    max_tokens: int
    temperature: float

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    provider_info: ProviderInfo
    version: str = "1.0.0"

class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime 