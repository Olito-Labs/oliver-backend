from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, List, Dict, Any
import json
import uuid
from datetime import datetime

from app.models.api import ChatRequest, ChatResponse, ChatMessage, StreamChunk
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api", tags=["chat"])

def _convert_messages_to_openai_format(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    """Convert ChatMessage list to OpenAI Responses API input format."""
    openai_messages = []
    
    for message in messages:
        # Don't add custom IDs to messages - let OpenAI handle internal message IDs
        # Only use response_id for conversation state via previous_response_id parameter
        openai_messages.append({
            "role": "user" if message.sender == "user" else "assistant",
            "content": [{"type": "input_text" if message.sender == "user" else "output_text", "text": message.content}]
        })
    
    return openai_messages

def _create_oliver_system_prompt(analysis_type: str) -> str:
    """Create system prompt with industry/institution validation first."""
    
    return """You are Oliver, a regulatory risk management expert. You are the word's foremost authority on how to deal with regulatory risk in a bottum-up, first principles, fit-for-purpose, and evidence-based manner.
Given an institution's name, confirm the institution's details. For instance, if it's a bank, search and provide accurate results for the following at the very least:
   - Bank/institution name and holding company (if different)
   - Charter type (national, state member, state non-member, credit union, etc.)
   - Asset size tier and latest figures (cite source: "e.g., $47bn assets, 2024 Q1 Call Report")
   - Primary regulators (Fed, OCC, FDIC, CFPB, state, etc.)

   Provide a summary of the institution's details in a bullet list format.


**Style:** Professional, evidence-based, concise. Always cite data sources. Write in bullet lists."""
    


@router.post("/chat")
async def chat_non_streaming(request: ChatRequest) -> ChatResponse:
    """Non-streaming chat endpoint with conversation state management."""
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not initialized")
        
        # Convert messages to OpenAI format
        openai_messages = _convert_messages_to_openai_format(request.messages)
        
        # Create system prompt based on analysis type
        system_prompt = _create_oliver_system_prompt(request.analysis_type)
        
        # Prepare tools - include web search for research capabilities
        web_search_tool_name = openai_manager.get_web_search_tool_name()
        tools = [
            {
                "type": web_search_tool_name,
                "user_location": {
                    "type": "approximate",
                    "country": "US"
                },
                "search_context_size": "medium"
            }
        ]
        
        # Build request parameters
        request_params = {
            "model": settings.OPENAI_MODEL,
            "input": openai_messages,
            "instructions": system_prompt,
            "max_output_tokens": settings.MAX_TOKENS,
            "temperature": settings.TEMPERATURE,
            "tools": tools,
            "stream": False,
            "store": True,
            "text": {"format": {"type": "text"}},
            "reasoning": {}
        }
        
        # Critical: Include previous_response_id for conversation state
        if request.previous_response_id:
            request_params["previous_response_id"] = request.previous_response_id
        
        # Call OpenAI Responses API
        response = client.responses.create(**request_params)
        
        # Extract response text
        response_text = ""
        if response.output and len(response.output) > 0:
            message_output = response.output[0]
            if hasattr(message_output, 'content') and len(message_output.content) > 0:
                response_text = message_output.content[0].text
        
        # Create assistant response
        assistant_message = ChatMessage(
            id=str(uuid.uuid4()),
            content=response_text,
            sender="assistant",
            timestamp=datetime.now(),
            metadata={
                "analysis_type": request.analysis_type,
                "response_id": response.id,
                "previous_response_id": request.previous_response_id
            }
        )
        
        return ChatResponse(
            message=assistant_message,
            artifacts=[],  # Can be enhanced later with artifact detection
            reasoning="",
            analysis_type=request.analysis_type
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

def _build_model_specific_params(openai_messages, system_prompt, tools):
    """Build request parameters specific to the model type.
    
    o3 models have different parameter support:
    - ❌ temperature, top_p (sampling parameters not supported)
    - ✅ reasoning.effort and reasoning.summary (o3-specific)
    - ⚠️  reasoning summary may be empty in ~90% of responses (known issue)
    
    Other models (GPT-4.1, etc.):
    - ✅ temperature, top_p (standard sampling parameters)
    - ⚠️  reasoning parameter may not be supported
    """
    
    # Base parameters that work for all models
    base_params = {
        "model": settings.OPENAI_MODEL,
        "input": openai_messages,
        "instructions": system_prompt,
        "max_output_tokens": settings.MAX_TOKENS,
        "tools": tools,
        "stream": True,
        "store": True,
        "text": {
            "format": {
                "type": "text"
            }
        }
    }
    
    # o3 model specific parameters
    if settings.OPENAI_MODEL.startswith("o3"):
        # o3 doesn't support temperature, top_p or other sampling parameters
        # but supports reasoning configuration
        base_params["reasoning"] = {
            "effort": "medium",
            "summary": "detailed"
        }
        print(f"[DEBUG] Using o3 model parameters (no temperature/top_p)")
    else:
        # For other models (GPT-4.1, etc.), include sampling parameters
        base_params["temperature"] = settings.TEMPERATURE
        # Note: reasoning parameter may not be supported by older models
        base_params["reasoning"] = {}
        print(f"[DEBUG] Using standard model parameters (with temperature={settings.TEMPERATURE})")
    
    return base_params

@router.post("/chat/stream")
async def chat_streaming(request: ChatRequest):
    """Streaming chat endpoint with function calling and chain of thought display."""
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            client = openai_manager.get_client()
            if not client:
                raise HTTPException(status_code=500, detail="OpenAI client not initialized")
            
            # Convert ChatMessage list to OpenAI format
            openai_messages = _convert_messages_to_openai_format(request.messages)
            
            # Create system prompt
            system_prompt = _create_oliver_system_prompt(request.analysis_type)
            
            # Get the appropriate web search tool name
            web_search_tool_name = openai_manager.get_web_search_tool_name()
            
            # Build tools array
            tools = [
                {
                    "type": web_search_tool_name,
                    "user_location": {
                        "type": "approximate", 
                        "country": "US"
                    },
                    "search_context_size": "medium"
                }
            ]
            
            # Build model-specific request parameters
            request_params = _build_model_specific_params(openai_messages, system_prompt, tools)
            
            # Critical: Include previous_response_id for conversation state
            if request.previous_response_id:
                print(f"[DEBUG] Using previous_response_id: {request.previous_response_id}")
                request_params["previous_response_id"] = request.previous_response_id
            else:
                print("[DEBUG] No previous_response_id provided (first message)")
            
            # Call OpenAI Responses API with streaming
            stream = client.responses.create(**request_params)
            
            response_id = None
            accumulated_text = ""
            function_calls = {}  # Track function calls by call_id
            reasoning_messages = []  # Accumulate reasoning for metadata
            current_reasoning_buffer = ""  # Buffer for accumulating reasoning deltas
            
            for chunk in stream:
                # Debug: Log all chunk types we receive
                print(f"[DEBUG] Received chunk type: {chunk.type}")
                
                # Extra debugging for function calls
                if hasattr(chunk, 'item'):
                    print(f"[DEBUG] Chunk has item: {getattr(chunk.item, 'type', 'no-type')} - {getattr(chunk.item, 'name', 'no-name')}")
                if hasattr(chunk, '__dict__'):
                    print(f"[DEBUG] Chunk attributes: {list(chunk.__dict__.keys())}")
                
                if chunk.type == "response.created":
                    response_id = chunk.response.id
                    print(f"[DEBUG] OpenAI Response ID created: {response_id}")
                    yield f"data: {json.dumps({'type': 'status', 'content': '🤖 Oliver is analyzing your request...', 'done': False})}\n\n"
                
                elif chunk.type == "response.in_progress":
                    yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Thinking about the best approach...', 'done': False})}\n\n"
                
                elif chunk.type == "response.output_item.added":
                    # New output item (function call, web search call, or text) started
                    print(f"[DEBUG] Output item added: {getattr(chunk, 'item', 'unknown')}")
                    if hasattr(chunk, 'item'):
                        if hasattr(chunk.item, 'type') and chunk.item.type == "function_call":
                            tool_name = getattr(chunk.item, 'name', 'unknown')
                            call_id = getattr(chunk.item, 'call_id', 'unknown')
                            
                            # Initialize function call tracking
                            function_calls[call_id] = {
                                'name': tool_name,
                                'arguments': '',
                                'call_id': call_id,
                                'id': getattr(chunk.item, 'id', 'unknown')
                            }
                            
                            # Only show essential reasoning for tool use
                            if tool_name in ['web_search', 'web_search_preview']:
                                # Just indicate we're using search, details will come later
                                reasoning_msg = '🔍 Researching current information...'
                                reasoning_messages.append(reasoning_msg)
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_msg, 'done': False})}\n\n"
                            else:
                                reasoning_msg = f"🔧 Using {tool_name}..."
                                reasoning_messages.append(reasoning_msg)
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_msg, 'done': False})}\n\n"
                        
                        elif hasattr(chunk.item, 'type') and chunk.item.type == "web_search_call":
                            # Handle web search call output items - no additional message needed
                            search_id = getattr(chunk.item, 'id', 'unknown')
                            print(f"[DEBUG] Web search call started: {search_id}")
                            # Skip the redundant "Initiating web search" message
                        
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'content': '📝 Preparing my response...', 'done': False})}\n\n"
                
                elif chunk.type == "response.function_call_arguments.delta":
                    # Stream function call arguments building
                    if hasattr(chunk, 'item_id'):
                        call_id = None
                        # Find the call_id from our tracking
                        for tracked_call_id, call_data in function_calls.items():
                            if call_data['id'] == chunk.item_id:
                                call_id = tracked_call_id
                                break
                        
                        if call_id and hasattr(chunk, 'delta'):
                            function_calls[call_id]['arguments'] += chunk.delta
                            # Skip the verbose "Building search query" messages
                
                elif chunk.type == "response.function_call_arguments.done":
                    # Function call arguments complete - execute the function
                    print(f"[DEBUG] Function call arguments done")
                    
                    # Find the completed function call
                    for call_id, call_data in function_calls.items():
                        if call_data['arguments']:
                            try:
                                args = json.loads(call_data['arguments'])
                                tool_name = call_data['name']
                                
                                # Show what we're searching for - this is the valuable information!
                                if tool_name in ['web_search', 'web_search_preview'] and 'query' in args:
                                    search_query = args['query']
                                    search_msg = f'🔍 Searching for: "{search_query}"'
                                    reasoning_messages.append(search_msg)
                                    yield f"data: {json.dumps({'type': 'reasoning', 'content': search_msg, 'done': False})}\n\n"
                                
                                # Skip verbose processing messages - let the user focus on the actual response
                                
                            except json.JSONDecodeError as e:
                                print(f"[DEBUG] Error parsing function arguments: {e}")
                                error_msg = '⚠️ Having trouble with the search parameters, continuing...'
                                reasoning_messages.append(error_msg)
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': error_msg, 'done': False})}\n\n"
                
                elif chunk.type == "response.output_text.delta":
                    # Real-time token streaming - this is the key for true streaming!
                    print(f"[DEBUG] Text delta received: '{chunk.delta}'")
                    if hasattr(chunk, 'delta'):
                        token_text = chunk.delta
                        accumulated_text += token_text
                        
                        # Open canvas on first content token if not already opened
                        if len(accumulated_text) <= len(token_text):  # First token
                            yield f"data: {json.dumps({'type': 'canvas_ready', 'content': '', 'done': False})}\n\n"
                        
                        # Send final content to canvas instead of chat
                        yield f"data: {json.dumps({'type': 'canvas_content', 'content': token_text, 'done': False})}\n\n"
                
                elif chunk.type == "response.output_item.done":
                    # Output item complete
                    print(f"[DEBUG] Output item done")
                    if accumulated_text:  # Only show if we have text content
                        yield f"data: {json.dumps({'type': 'status', 'content': '✅ Response ready', 'done': False})}\n\n"
                
                elif chunk.type == "response.content_part.done":
                    # Content part complete - this is backup in case deltas were missed
                    print(f"[DEBUG] Content part done, checking for missing content")
                    if hasattr(chunk, 'part') and hasattr(chunk.part, 'text'):
                        complete_text = chunk.part.text
                        print(f"[DEBUG] Complete text length: {len(complete_text)}, accumulated: {len(accumulated_text)}")
                        if complete_text != accumulated_text:
                            # Send any missing content
                            missing_content = complete_text[len(accumulated_text):]
                            if missing_content:
                                print(f"[DEBUG] Sending missing content: {len(missing_content)} chars")
                                accumulated_text = complete_text
                                yield f"data: {json.dumps({'type': 'content', 'content': missing_content, 'done': False})}\n\n"
                
                elif chunk.type == "response.completed":
                    # Flush any final reasoning buffer content
                    if current_reasoning_buffer.strip():
                        reasoning_content = current_reasoning_buffer.strip()
                        reasoning_messages.append(reasoning_content)
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_content, 'done': False})}\n\n"
                        current_reasoning_buffer = ""
                    
                    # Send completion signal with conversation state AND accumulated reasoning
                    print(f"[DEBUG] Response completed. Final accumulated text length: {len(accumulated_text)}")
                    print(f"[DEBUG] Accumulated reasoning messages: {len(reasoning_messages)}")
                    print(f"[DEBUG] Sending response_id to frontend: {response_id}")
                    
                    completion_metadata = {
                        'analysis_type': request.analysis_type,
                        'response_id': response_id,
                        'previous_response_id': request.previous_response_id,
                        'full_response': accumulated_text,
                        'conversation_turns': len(request.messages),
                        'function_calls_used': len(function_calls),
                        'reasoning': '\n'.join(reasoning_messages) if reasoning_messages else ''  # KEY: Send accumulated reasoning
                    }
                    yield f"data: {json.dumps({'type': 'done', 'content': '', 'done': True, 'metadata': completion_metadata})}\n\n"
                    break
                
                # Handle web search specific events - simplified
                elif chunk.type == "response.web_search_call.completed":
                    # Only show completion, skip the progress messages
                    reasoning_msg = '✅ Search completed'
                    reasoning_messages.append(reasoning_msg)
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_msg, 'done': False})}\n\n"
                
                # Handle o3 detailed reasoning events - enhanced to capture all reasoning content
                elif chunk.type == "response.reasoning.started":
                    reasoning_msg = '🧠 Analyzing your request...'
                    reasoning_messages.append(reasoning_msg)
                    yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_msg, 'done': False})}\n\n"
                
                elif chunk.type == "response.reasoning.delta":
                    # Stream detailed reasoning content from o3 - accumulate and send in meaningful chunks
                    if hasattr(chunk, 'delta') and chunk.delta:
                        current_reasoning_buffer += chunk.delta
                        
                        # Send reasoning when we hit sentence boundaries or reach reasonable length
                        if (current_reasoning_buffer.endswith(('.', '!', '?', '\n\n')) or 
                            len(current_reasoning_buffer) > 100):
                            
                            reasoning_content = current_reasoning_buffer.strip()
                            if reasoning_content:
                                reasoning_messages.append(reasoning_content)
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_content, 'done': False})}\n\n"
                                current_reasoning_buffer = ""
                
                elif chunk.type == "response.reasoning_summary_text.delta":
                    # Handle reasoning summary text deltas - accumulate similarly
                    if hasattr(chunk, 'delta') and chunk.delta:
                        current_reasoning_buffer += chunk.delta
                        
                        # Send when we have complete thoughts
                        if (current_reasoning_buffer.endswith(('.', '!', '?', '\n\n')) or 
                            len(current_reasoning_buffer) > 100):
                            
                            reasoning_content = current_reasoning_buffer.strip()
                            if reasoning_content:
                                reasoning_messages.append(reasoning_content)
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_content, 'done': False})}\n\n"
                                current_reasoning_buffer = ""
                
                elif chunk.type == "response.reasoning.completed":
                    # Flush any remaining reasoning buffer content first
                    if current_reasoning_buffer.strip():
                        reasoning_content = current_reasoning_buffer.strip()
                        reasoning_messages.append(reasoning_content)
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_content, 'done': False})}\n\n"
                        current_reasoning_buffer = ""
                    
                    # Final reasoning summary from o3
                    if hasattr(chunk, 'reasoning') and chunk.reasoning and chunk.reasoning.strip():
                        # Stream the complete reasoning summary
                        detailed_reasoning = chunk.reasoning.strip()
                        reasoning_messages.append(detailed_reasoning)
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': detailed_reasoning, 'done': False})}\n\n"
                    
                elif chunk.type == "response.reasoning_summary_text.done":
                    # Reasoning summary text completed
                    if hasattr(chunk, 'text') and chunk.text and chunk.text.strip():
                        reasoning_summary = chunk.text.strip()
                        reasoning_messages.append(reasoning_summary)
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_summary, 'done': False})}\n\n"
                
                else:
                    # Log any unhandled chunk types - especially reasoning-related ones
                    print(f"[DEBUG] Unhandled chunk type: {chunk.type}")
                    if 'reasoning' in chunk.type.lower():
                        print(f"[REASONING] Missed reasoning event: {chunk.type}")
                        if hasattr(chunk, '__dict__'):
                            print(f"[REASONING] Attributes: {list(chunk.__dict__.keys())}")
                            for attr in ['delta', 'text', 'reasoning', 'content']:
                                if hasattr(chunk, attr):
                                    value = getattr(chunk, attr)
                                    if value:
                                        print(f"[REASONING] {attr}: {value}")
                    if hasattr(chunk, '__dict__'):
                        print(f"[DEBUG] Chunk attributes: {list(chunk.__dict__.keys())}")
                 
        except Exception as e:
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
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.get("/provider/info")
async def get_provider_info():
    """Get current provider information."""
    return openai_manager.get_current_provider_info() 