from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator, Dict, Any
import json
import uuid
from datetime import datetime

from app.models.api import ChatMessage, ChatRequest
from app.llm_providers import openai_manager
from app.auth import get_current_user
from app.config import settings
from app.supabase_client import supabase

router = APIRouter(prefix="/api/kannada-expert", tags=["kannada-expert"])

class KannadaExpertRequest(BaseModel):
    """Request model for Kannada Expert workflow."""
    message: str
    study_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stream: bool = True

class KannadaExpertResponse(BaseModel):
    """Response model for Kannada Expert workflow."""
    response: str
    conversation_id: str
    study_id: Optional[str] = None
    timestamp: datetime
    model_used: str
    response_id: Optional[str] = None

class KannadaConversationCreate(BaseModel):
    """Model for creating a new Kannada conversation."""
    title: str = "Kannada Translation Session"
    description: Optional[str] = None

def _create_kannada_system_prompt() -> str:
    """Create specialized system prompt for Kannada translation expert."""
    return """You are a galli boy from mandya and live in bangalore and mysore. You are a helpful assistant, but only talk in street kannada - be a cool boli maga and treat your friends like your boys"""

@router.post("/chat")
async def kannada_expert_chat(
    request: KannadaExpertRequest,
    user=Depends(get_current_user)
):
    """
    Kannada Expert chat endpoint with Supabase integration for production.
    Handles both streaming and non-streaming responses.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not initialized")
        
        # Generate or use existing conversation ID
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Create system prompt for Kannada expert
        system_prompt = _create_kannada_system_prompt()
        
        # Build request parameters for GPT-5 Nano (optimized for speed)
        request_params = {
            "model": "gpt-5-nano",  # Use GPT-5 Nano specifically for faster translation
            "input": request.message,
            "instructions": system_prompt,
            "max_output_tokens": 1000,  # Reduced for faster responses
            "store": True,
            "metadata": {"purpose": "kannada-expert", "user_id": user['uid']},
        }
        
        # GPT-5 Nano specific parameters (optimized for speed but with reasoning)
        request_params["reasoning"] = {"effort": "low", "summary": "detailed"}  # Low effort for speed but still show reasoning
        request_params["text"] = {"verbosity": "medium"}  # Medium verbosity for clear translations
        
        if request.stream:
            # Streaming response
            return StreamingResponse(
                _generate_streaming_response(client, request_params, conversation_id, request.study_id, user),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )
        else:
            # Non-streaming response
            response = client.responses.create(**request_params)
            
            # Extract response text
            response_text = ""
            if response.output and len(response.output) > 0:
                message_output = response.output[0]
                if hasattr(message_output, 'content') and len(message_output.content) > 0:
                    response_text = message_output.content[0].text
            
            # Store conversation in database
            await _store_conversation_message(user['uid'], request.study_id, request.message, response_text, conversation_id)
            
            return KannadaExpertResponse(
                response=response_text,
                conversation_id=conversation_id,
                study_id=request.study_id,
                timestamp=datetime.now(),
                model_used="gpt-5-nano",
                response_id=getattr(response, 'id', None)
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Kannada expert request: {str(e)}")

async def _generate_streaming_response(client, request_params, conversation_id, study_id, user) -> AsyncGenerator[str, None]:
    """Generate streaming response for Kannada expert with conversation persistence."""
    try:
        # Use context manager for proper stream handling
        with client.responses.stream(**request_params) as stream:
            response_id = None
            accumulated_text = ""
            accumulated_reasoning = ""

            # Emit a normalized start event with metadata
            start_payload = {
                "type": "start",
                "metadata": {
                    "conversation_id": conversation_id,
                    "model_used": "gpt-5-nano",
                }
            }
            yield f"data: {json.dumps(start_payload)}\n\n"

            for event in stream:
                et = getattr(event, "type", None)

                if et == "response.created":
                    response_id = getattr(getattr(event, "response", None), "id", None)

                elif et == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        accumulated_text += delta
                        yield f"data: {json.dumps({'type': 'content', 'content': delta, 'done': False})}\n\n"

                # Robust reasoning matching - handles any reasoning event
                elif et and et.startswith("response.reasoning"):
                    delta = getattr(event, "delta", "")
                    if delta:
                        accumulated_reasoning += delta
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta, 'done': False, 'channel': 'full'})}\n\n"

                elif et == "response.refusal.delta":
                    # Surface refusals into reasoning pane so the user sees *why*
                    delta = getattr(event, "delta", "")
                    if delta:
                        accumulated_reasoning += delta
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta, 'done': False, 'channel': 'refusal'})}\n\n"

                elif et in ("response.error", "response.failed"):
                    msg = getattr(event, "error", "Unknown error")
                    yield f"data: {json.dumps({'type': 'error', 'content': str(msg), 'done': True})}\n\n"
                    return

                elif et == "response.completed":
                    # Explicit completion handling
                    break

            # Finalize using the SDK's final response to avoid drift
            final = stream.get_final_response()
            if not accumulated_text:
                try:
                    accumulated_text = getattr(final, "output_text", "") or ""
                except Exception:
                    pass

            await _store_conversation_message(
                user['uid'], study_id, request_params['input'],
                accumulated_text, conversation_id, accumulated_reasoning
            )

            completion_data = {
                'type': 'done',
                'content': '',
                'done': True,
                'metadata': {
                    'conversation_id': conversation_id,
                    'response_id': response_id or getattr(final, "id", None),
                    'full_response': accumulated_text,
                    'model_used': "gpt-5-nano",
                    'timestamp': datetime.now().isoformat(),
                    'study_id': study_id
                }
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
        
    except Exception as e:
        error_chunk = {
            "type": "error",
            "content": f"Error generating response: {str(e)}",
            "done": True,
            "error": str(e)
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

async def _store_conversation_message(user_id: str, study_id: Optional[str], user_message: str, assistant_response: str, conversation_id: str, reasoning: Optional[str] = None):
    """Store conversation messages in Supabase for persistence."""
    try:
        # Store user message
        user_message_data = {
            'id': str(uuid.uuid4()),
            'study_id': study_id,
            'content': user_message,
            'sender': 'user',
            'metadata': {
                'conversation_id': conversation_id,
                'workflow_type': 'kannada-expert'
            },
            'created_at': datetime.now().isoformat()
        }
        
        # Store assistant response
        assistant_message_data = {
            'id': str(uuid.uuid4()),
            'study_id': study_id,
            'content': assistant_response,
            'sender': 'assistant',
            'metadata': {
                'conversation_id': conversation_id,
                'workflow_type': 'kannada-expert',
                'model_used': "gpt-5-nano"
            },
            'reasoning': reasoning,
            'created_at': datetime.now().isoformat()
        }
        
        # Insert both messages
        if study_id:  # Only store if we have a study context
            supabase.table('messages').insert([user_message_data, assistant_message_data]).execute()
            
            # Update study's last_message_at
            supabase.table('studies').update({
                'last_message_at': datetime.now().isoformat()
            }).eq('id', study_id).eq('user_id', user_id).execute()
            
    except Exception as e:
        print(f"Warning: Failed to store conversation: {e}")
        # Don't fail the request if storage fails

@router.post("/conversations")
async def create_kannada_conversation(
    request: KannadaConversationCreate,
    user=Depends(get_current_user)
):
    """Create a new Kannada Expert conversation/study."""
    try:
        study_data = {
            'id': str(uuid.uuid4()),
            'user_id': user['uid'],
            'title': request.title,
            'description': request.description,
            'workflow_type': 'kannada-expert',
            'intent': 'kannada-expert',
            'current_step': 0,
            'workflow_status': 'in_progress',
            'workflow_data': {
                'expert_type': 'kannada-translation',
                'conversation_started_at': datetime.now().isoformat()
            },
            'status': 'active'
        }
        
        result = supabase.table('studies').insert(study_data).execute()
        
        if result.data:
            return {"study": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create Kannada Expert conversation")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating Kannada Expert conversation: {str(e)}")

@router.get("/conversations")
async def get_kannada_conversations(user=Depends(get_current_user)):
    """Get all Kannada Expert conversations for the current user."""
    try:
        result = supabase.table('studies')\
            .select("*")\
            .eq('user_id', user['uid'])\
            .eq('workflow_type', 'kannada-expert')\
            .order('last_message_at', desc=True)\
            .execute()
            
        return {"conversations": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Kannada Expert conversations: {str(e)}")

@router.get("/status")
async def get_kannada_expert_status():
    """Get the status of the Kannada Expert workflow."""
    try:
        client = openai_manager.get_client()
        provider_info = openai_manager.get_current_provider_info()
        
        return {
            "status": "ready" if client else "unavailable",
            "workflow": "kannada-expert",
            "model": "gpt-5-nano",  # Specifically using GPT-5 Nano for speed
            "base_model": settings.OPENAI_MODEL,  # Show the configured base model too
            "provider_info": provider_info,
            "optimization": "speed-optimized for translation tasks",
            "capabilities": [
                "English to Kannada translation",
                "Kannada to English translation", 
                "Grammar explanations",
                "Cultural context",
                "Conversation persistence"
            ],
            "endpoints": {
                "chat": "/api/kannada-expert/chat",
                "conversations": "/api/kannada-expert/conversations",
                "status": "/api/kannada-expert/status"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/test")
async def test_kannada_expert(user=Depends(get_current_user)):
    """Quick test endpoint to verify the Kannada Expert is working."""
    try:
        test_request = KannadaExpertRequest(
            message="Translate: Good morning, how are you today?",
            stream=False
        )
        
        response = await kannada_expert_chat(test_request, user)
        
        return {
            "test_status": "success",
            "test_response": response,
            "message": "Kannada Expert workflow is working correctly!"
        }
    except Exception as e:
        return {
            "test_status": "failed",
            "error": str(e),
            "message": "Kannada Expert workflow encountered an error."
        }
