from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json
import uuid
from datetime import datetime

from app.models.api import ChatRequest, ChatResponse, ChatMessage, StreamChunk
from app.dspy_modules.modules import assistant, streaming_assistant
from app.llm_providers import llm_manager

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
async def chat_non_streaming(request: ChatRequest) -> ChatResponse:
    """Non-streaming chat endpoint."""
    try:
        # Get the last message from the user
        user_message = request.messages[-1]
        
        # Process with DSPy assistant
        result = assistant(
            query=user_message.content,
            context=request.context,
            analysis_type=request.analysis_type
        )
        
        # Create assistant response message
        assistant_message = ChatMessage(
            id=str(uuid.uuid4()),
            content=result["response"],
            sender="assistant",
            timestamp=datetime.now(),
            metadata={
                "analysis_type": result.get("type"),
                "reasoning": result.get("reasoning", "")
            }
        )
        
        return ChatResponse(
            message=assistant_message,
            artifacts=result.get("artifacts", []),
            reasoning=result.get("reasoning", ""),
            analysis_type=result.get("type", "general")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@router.post("/chat/stream")
async def chat_streaming(request: ChatRequest):
    """Streaming chat endpoint."""
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Get the last message from the user
            user_message = request.messages[-1]
            
            # Start streaming response
            async for chunk in streaming_assistant.stream_response(
                query=user_message.content,
                context=request.context,
                analysis_type=request.analysis_type
            ):
                # Format as SSE (Server-Sent Events)
                yield f"data: {json.dumps(chunk)}\n\n"
                
        except Exception as e:
            error_chunk = StreamChunk(
                type="error",
                content=f"Error: {str(e)}",
                done=True
            )
            yield f"data: {json.dumps(error_chunk.dict())}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@router.get("/provider/info")
async def get_provider_info():
    """Get current LLM provider information."""
    try:
        return llm_manager.get_current_provider_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting provider info: {str(e)}")

@router.post("/provider/switch")
async def switch_provider(request: dict):
    """Switch to a different LLM provider."""
    try:
        provider = request.get("provider")
        api_key = request.get("api_key")
        
        if not provider:
            raise HTTPException(status_code=400, detail="Provider is required")
        
        success = llm_manager.switch_provider(provider, api_key)
        
        if success:
            return {"message": f"Successfully switched to {provider}", "success": True}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to switch to {provider}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error switching provider: {str(e)}") 