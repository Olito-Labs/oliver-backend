from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal, Union
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
    previous_response_id: Optional[str] = None  # Critical: For conversation state management

class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    message: ChatMessage
    artifacts: Optional[List[Dict[str, Any]]] = []
    reasoning: Optional[str] = ""
    analysis_type: Optional[str] = ""

class StreamChunk(BaseModel):
    """Model for streaming response chunks from DSPy streaming."""
    type: Literal["content", "reasoning", "status", "artifacts", "done", "error"]
    content: Union[str, List[Dict[str, Any]]]
    done: bool = False
    metadata: Optional[Dict[str, Any]] = None
    field: Optional[str] = None  # DSPy field name (response, analysis, findings, rationale)
    error: Optional[str] = None  # Error details for error type

class DSPyStreamResponse(BaseModel):
    """Model for DSPy StreamResponse objects."""
    predict_name: str
    signature_field_name: str
    chunk: str

class DSPyStatusMessage(BaseModel):
    """Model for DSPy StatusMessage objects."""
    message: str

class DSPyPrediction(BaseModel):
    """Model for DSPy Prediction objects."""
    # This will contain the final prediction fields
    # Content varies based on signature used
    content: Dict[str, Any]

class StreamingEvent(BaseModel):
    """Unified model for all streaming events."""
    event_type: Literal["stream_response", "status_message", "prediction", "oliver_chunk"]
    data: Union[DSPyStreamResponse, DSPyStatusMessage, DSPyPrediction, StreamChunk]
    timestamp: datetime = Field(default_factory=datetime.now)

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