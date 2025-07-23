from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, List, Dict
import json
import uuid
from datetime import datetime

from app.models.api import ChatRequest, ChatResponse, ChatMessage, StreamChunk
from app.dspy_modules.modules import assistant
from app.dspy_modules.streaming import streaming_assistant
from app.llm_providers import llm_manager

router = APIRouter(prefix="/api", tags=["chat"])

def _convert_messages_to_history(messages: List[ChatMessage]) -> List[Dict[str, str]]:
    """
    Convert ChatMessage list to conversation history format for DSPy.
    
    Args:
        messages: List of ChatMessage objects
        
    Returns:
        List of conversation turns in {"query": "...", "response": "..."} format
    """
    conversation_history = []
    current_query = None
    
    for message in messages[:-1]:  # Exclude the last message (current query)
        if message.sender == "user":
            current_query = message.content
        elif message.sender == "assistant" and current_query:
            conversation_history.append({
                "query": current_query,
                "response": message.content
            })
            current_query = None
    
    return conversation_history

@router.post("/chat")
async def chat_non_streaming(request: ChatRequest) -> ChatResponse:
    """Non-streaming chat endpoint with conversation memory."""
    try:
        # Get the current user message
        user_message = request.messages[-1]
        
        # Convert message history to conversation format
        conversation_history = _convert_messages_to_history(request.messages)
        
        # Process with DSPy assistant including conversation history
        result = assistant(
            query=user_message.content,
            conversation_history=conversation_history,
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
                "reasoning": result.get("reasoning", ""),
                "conversation_turns": len(conversation_history)
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
    """Streaming chat endpoint with DSPy streaming and conversation memory."""
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Get the current user message
            user_message = request.messages[-1]
            
            # Convert message history to conversation format
            conversation_history = _convert_messages_to_history(request.messages)
            
            # Start DSPy streaming with conversation history
            async for chunk in streaming_assistant.stream_response(
                query=user_message.content,
                conversation_history=conversation_history,
                context=request.context,
                analysis_type=request.analysis_type
            ):
                # The chunk is already in the correct format from our streaming module
                # Add conversation context to metadata for done chunks
                if chunk.get("type") == "done":
                    chunk["metadata"] = chunk.get("metadata", {})
                    chunk["metadata"]["conversation_turns"] = len(conversation_history)
                    # Add message ID for frontend to track
                    chunk["metadata"]["message_id"] = str(uuid.uuid4())
                
                # Format as SSE (Server-Sent Events)
                yield f"data: {json.dumps(chunk)}\n\n"
                
        except Exception as e:
            # Return error in Oliver streaming format
            error_chunk = {
                "type": "error",
                "content": f"Error processing request: {str(e)}",
                "done": True,
                "error": str(e)
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",  # For CORS in development
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.post("/chat/stream/debug")
async def chat_streaming_debug(request: ChatRequest):
    """Debug endpoint to test raw DSPy streaming without SSE formatting."""
    try:
        # Get the current user message
        user_message = request.messages[-1]
        
        # Convert message history to conversation format
        conversation_history = _convert_messages_to_history(request.messages)
        
        # Collect all streaming chunks for debugging
        chunks = []
        async for chunk in streaming_assistant.stream_response(
            query=user_message.content,
            conversation_history=conversation_history,
            context=request.context,
            analysis_type=request.analysis_type
        ):
            chunks.append(chunk)
        
        return {
            "total_chunks": len(chunks),
            "chunks": chunks,
            "conversation_turns": len(conversation_history),
            "analysis_type": request.analysis_type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in debug streaming: {str(e)}")

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