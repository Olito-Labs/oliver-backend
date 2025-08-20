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

router = APIRouter(prefix="/api/startup-advisor", tags=["startup-advisor"])

# Simple in-memory conversation threading (use database in production for persistence)
CONVERSATION_RESPONSE_IDS: Dict[str, str] = {}

class StartupAdvisorRequest(BaseModel):
    """Request model for Startup Advisor workflow."""
    message: str
    study_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stream: bool = True

class StartupAdvisorResponse(BaseModel):
    """Response model for Startup Advisor workflow."""
    response: str
    conversation_id: str
    study_id: Optional[str] = None
    timestamp: datetime
    model_used: str
    response_id: Optional[str] = None

class StartupAdvisorConversationCreate(BaseModel):
    """Model for creating a new Startup Advisor conversation."""
    title: str = "Startup Advisor Session"
    description: Optional[str] = None

def _create_startup_advisor_system_prompt() -> str:
    """Create specialized system prompt for Startup Advisor based on Paul Graham's writings."""
    return """You are Oliver, a startup advisor deeply versed in Paul Graham's philosophy and writings. You provide thoughtful, practical advice to entrepreneurs based on Paul's insights from Y Combinator and his essays.

Your expertise covers:
- Startup fundamentals and early-stage strategy
- Product development and finding product-market fit
- Fundraising, investors, and Y Combinator insights
- Building great teams and company culture
- Technical founder advice and scaling challenges
- Market timing and competitive strategy

Style Guidelines:
- Give direct, actionable advice in Paul Graham's clear, thoughtful style
- Reference specific concepts from his essays when relevant
- Be encouraging but realistic about startup challenges
- Focus on what matters most for early-stage companies
- Ask clarifying questions when you need more context
- Share relevant examples and analogies when helpful

Always ground your advice in Paul's core principles: build something people want, talk to users, iterate quickly, and focus on growth. Be the advisor Paul Graham would be - wise, practical, and genuinely helpful to founders."""

@router.post("/chat")
async def startup_advisor_chat(
    request: StartupAdvisorRequest,
    user=Depends(get_current_user)
):
    """
    Startup Advisor chat endpoint with Supabase integration for production.
    Handles both streaming and non-streaming responses with conversation memory.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not initialized")
        
        # Generate or use existing conversation ID
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Get previous response ID for conversation continuity
        previous_response_id = CONVERSATION_RESPONSE_IDS.get(conversation_id)
        
        # Create system prompt for Startup Advisor
        system_prompt = _create_startup_advisor_system_prompt()
        
        # Build request parameters for GPT-5 Nano (optimized for speed)
        request_params = {
            "model": "gpt-5-nano",  # Use GPT-5 Nano specifically for faster translation
            "input": request.message,
            "instructions": system_prompt,
            "max_output_tokens": 1000,  # Reduced for faster responses
            "store": True,
            "metadata": {"purpose": "startup-advisor", "user_id": user['uid']},
        }
        
        # Add previous response ID for conversation memory
        if previous_response_id:
            request_params["previous_response_id"] = previous_response_id
        
        # GPT-5 Nano specific parameters (optimized for thoughtful startup advice)
        request_params["reasoning"] = {"effort": "medium", "summary": "detailed"}  # Medium effort for thoughtful advice
        request_params["text"] = {"verbosity": "medium"}  # Medium verbosity for clear advice
        
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
            
            # Store conversation in database and response ID for memory
            response_id = getattr(response, 'id', None)
            if response_id:
                CONVERSATION_RESPONSE_IDS[conversation_id] = response_id
            await _store_conversation_message(user['uid'], request.study_id, request.message, response_text, conversation_id)
            
            return StartupAdvisorResponse(
                response=response_text,
                conversation_id=conversation_id,
                study_id=request.study_id,
                timestamp=datetime.now(),
                model_used="gpt-5-nano",
                response_id=getattr(response, 'id', None)
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Startup Advisor request: {str(e)}")

async def _generate_streaming_response(client, request_params, conversation_id, study_id, user) -> AsyncGenerator[str, None]:
    """Generate streaming response for Startup Advisor with conversation persistence."""
    try:
        # Use correct streaming pattern as recommended
        stream = client.responses.create(stream=True, **request_params)
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
                # Explicit completion handling - but don't break, let the loop finish naturally
                pass

        # After the stream ends naturally, finalize the response
        # Store conversation in database
        await _store_conversation_message(
            user['uid'], study_id, request_params['input'],
            accumulated_text, conversation_id, accumulated_reasoning
        )

        # Store response ID for conversation memory
        if response_id:
            CONVERSATION_RESPONSE_IDS[conversation_id] = response_id

        completion_data = {
            'type': 'done',
            'content': '',
            'done': True,
            'metadata': {
                'conversation_id': conversation_id,
                'response_id': response_id,
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
                'workflow_type': 'startup-advisor'
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
                'workflow_type': 'startup-advisor',
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
async def create_startup_advisor_conversation(
    request: StartupAdvisorConversationCreate,
    user=Depends(get_current_user)
):
    """Create a new Startup Advisor conversation/study."""
    try:
        study_data = {
            'id': str(uuid.uuid4()),
            'user_id': user['uid'],
            'title': request.title,
            'description': request.description,
            'workflow_type': 'startup-advisor',
            'intent': 'startup-advisor',
            'current_step': 0,
            'workflow_status': 'in_progress',
            'workflow_data': {
                'expert_type': 'startup-advisor',
                'conversation_started_at': datetime.now().isoformat()
            },
            'status': 'active'
        }
        
        result = supabase.table('studies').insert(study_data).execute()
        
        if result.data:
            return {"study": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create Startup Advisor conversation")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating Startup Advisor conversation: {str(e)}")

@router.get("/conversations")
async def get_startup_advisor_conversations(user=Depends(get_current_user)):
    """Get all Startup Advisor conversations for the current user."""
    try:
        result = supabase.table('studies')\
            .select("*")\
            .eq('user_id', user['uid'])\
            .eq('workflow_type', 'startup-advisor')\
            .order('last_message_at', desc=True)\
            .execute()
            
        return {"conversations": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Startup Advisor conversations: {str(e)}")

@router.get("/status")
async def get_startup_advisor_status():
    """Get the status of the Startup Advisor workflow."""
    try:
        client = openai_manager.get_client()
        provider_info = openai_manager.get_current_provider_info()
        
        return {
            "status": "ready" if client else "unavailable",
            "workflow": "startup-advisor",
            "model": "gpt-5-nano",  # Using GPT-5 Nano for thoughtful but fast advice
            "base_model": settings.OPENAI_MODEL,  # Show the configured base model too
            "provider_info": provider_info,
            "optimization": "optimized for startup advice with Paul Graham insights",
            "capabilities": [
                "Startup strategy and fundamentals",
                "Product-market fit guidance", 
                "Fundraising and investor advice",
                "Y Combinator insights",
                "Technical founder support",
                "Paul Graham essay-based wisdom",
                "Conversation persistence"
            ],
            "endpoints": {
                "chat": "/api/startup-advisor/chat",
                "conversations": "/api/startup-advisor/conversations",
                "status": "/api/startup-advisor/status"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/test")
async def test_startup_advisor(user=Depends(get_current_user)):
    """Quick test endpoint to verify the Startup Advisor is working."""
    try:
        test_request = StartupAdvisorRequest(
            message="What's the most important thing for an early-stage startup to focus on?",
            stream=False
        )
        
        response = await startup_advisor_chat(test_request, user)
        
        return {
            "test_status": "success",
            "test_response": response,
            "message": "Startup Advisor workflow is working correctly!"
        }
    except Exception as e:
        return {
            "test_status": "failed",
            "error": str(e),
            "message": "Startup Advisor workflow encountered an error."
        }
