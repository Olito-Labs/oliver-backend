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
    temperature: Optional[float] = None
    reasoning_effort: Optional[str] = None
    reasoning_summary: Optional[str] = None
    note: Optional[str] = None

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

# Slide Generation Models
class SlideGenerationRequest(BaseModel):
    """Request model for slide generation."""
    slide_request: str = Field(..., description="Natural language description of the desired slide")
    css_framework: str = Field(default="olito-tech", description="CSS framework to use: 'olito-tech' or 'fulton-base'")
    model: str = Field(default="gpt-4", description="OpenAI model to use")

class SlideGenerationResponse(BaseModel):
    """Response model for slide generation."""
    slide_html: str = Field(..., description="Generated HTML slide code")
    framework_used: str = Field(..., description="CSS framework that was used")
    model_used: str = Field(..., description="Model that was used for generation")
    generation_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about generation")

class SlideFramework(BaseModel):
    """Model for available slide frameworks."""
    id: str = Field(..., description="Framework identifier")
    name: str = Field(..., description="Human-readable framework name")
    description: str = Field(..., description="Framework description")
    colors: Dict[str, str] = Field(..., description="Framework color palette")

class SlideExample(BaseModel):
    """Model for slide generation examples."""
    type: str = Field(..., description="Type of slide (title, metrics, problem, etc.)")
    request: str = Field(..., description="Example request text")
    description: str = Field(..., description="Description of what this example creates") 