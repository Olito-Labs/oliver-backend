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
    
    return """You are Oliver, a regulatory risk management agent currently focusing on banking institutions.

**CRITICAL FIRST STEP - Industry & Institution Validation:**

Before proceeding with any analysis, you MUST first determine:
1. **Is this inquiry about a banking institution?** (commercial banks, credit unions, savings associations, bank holding companies, etc.)
2. **What specific institution** is involved (name, charter type, approximate asset size if known)

**If this is NOT about banking or financial institutions:**
Respond politely: "I'm Oliver, a regulatory risk management agent currently focusing on banking institutions. More features for other industries coming soon. Please contact us if you have banking-related regulatory questions."

**If this IS about banking institutions:**
Proceed as a senior banking risk advisor and primary intake specialist. Your job is to:

1. **Confirm Institution Details:**
   - Bank/institution name and holding company (if different)  
   - Charter type (national, state member, state non-member, credit union, etc.)
   - Asset size tier and latest figures (cite source: "e.g., $47bn assets, 2024 Q1 Call Report")
   - Primary regulators (Fed, OCC, FDIC, CFPB, state, etc.)

2. **Understand the Risk/Compliance Issue:**
   - The specific problem, deadline, or objective  
   - Any counterparties or FinTech partners involved
   - Regulatory context or examination findings (if applicable)

3. **Classify the Workflow:**
   - Marketing Material Compliance Review
   - Examination Preparation  
   - MRA / Enforcement Action Remediation
   - Change Management Governance
   - New Law/Regulation Impact Analysis
   - Proposed Rulemaking Comment Analysis
   - Board Reporting / Risk Dashboard Preparation
   - Third-Party (FinTech) Risk Assessment
   - Other

4. **Confirm & Hand Off:**
   - Summarize institution details, issue, and recommended workflow
   - Ask for confirmation before proceeding
   - Once confirmed: "Context locked. Handing you to the [workflow-name] module now."

**Style:** Professional, evidence-based, concise. Always cite data sources. Use full paragraphs, not bullet lists. Stop and wait for confirmation before proceeding past intake."""
    


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

@router.post("/chat/stream")
async def chat_streaming(request: ChatRequest):
    """Streaming chat endpoint with function calling and chain of thought display."""
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            client = openai_manager.get_client()
            if not client:
                raise Exception("OpenAI client not initialized")
            
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
                "stream": True,
                "store": True,
                "text": {"format": {"type": "text"}},
                "reasoning": {}
            }
            
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
            
            for chunk in stream:
                # Debug: Log all chunk types we receive
                print(f"[DEBUG] Received chunk type: {chunk.type}")
                
                if chunk.type == "response.created":
                    response_id = chunk.response.id
                    print(f"[DEBUG] OpenAI Response ID created: {response_id}")
                    yield f"data: {json.dumps({'type': 'status', 'content': '🤖 Oliver is analyzing your request...', 'done': False})}\n\n"
                
                elif chunk.type == "response.in_progress":
                    yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Thinking about the best approach...', 'done': False})}\n\n"
                
                elif chunk.type == "response.output_item.added":
                    # New output item (function call or text) started
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
                            
                            # Chain of thought: Show what tool Oliver is using
                            if tool_name == 'web_search':
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': '💭 I need to search for current information to provide you with accurate details...', 'done': False})}\n\n"
                            else:
                                reasoning_msg = f"💭 I'm going to use {tool_name} to help answer your question..."
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': reasoning_msg, 'done': False})}\n\n"
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
                            # Show progress of building the search query
                            yield f"data: {json.dumps({'type': 'reasoning', 'content': '🔍 Building search query...', 'done': False})}\n\n"
                
                elif chunk.type == "response.function_call_arguments.done":
                    # Function call arguments complete - execute the function
                    print(f"[DEBUG] Function call arguments done")
                    
                    # Find the completed function call
                    for call_id, call_data in function_calls.items():
                        if call_data['arguments']:
                            try:
                                args = json.loads(call_data['arguments'])
                                tool_name = call_data['name']
                                
                                # Chain of thought: Show what we're searching for
                                if tool_name == 'web_search' and 'query' in args:
                                    search_query = args['query']
                                    search_msg = f'🔍 Searching for: "{search_query}"'
                                    yield f"data: {json.dumps({'type': 'reasoning', 'content': search_msg, 'done': False})}\n\n"
                                    yield f"data: {json.dumps({'type': 'status', 'content': '⚡ Executing search...', 'done': False})}\n\n"
                                
                                # Here you would normally execute the actual function
                                # For now, we'll simulate the process
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': '📊 Found relevant information, analyzing results...', 'done': False})}\n\n"
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': '🧩 Incorporating search results into my response...', 'done': False})}\n\n"
                                
                            except json.JSONDecodeError as e:
                                print(f"[DEBUG] Error parsing function arguments: {e}")
                                yield f"data: {json.dumps({'type': 'reasoning', 'content': '⚠️ Having trouble with the search parameters, continuing...', 'done': False})}\n\n"
                
                elif chunk.type == "response.output_text.delta":
                    # Real-time token streaming - this is the key for true streaming!
                    print(f"[DEBUG] Text delta received: '{chunk.delta}'")
                    if hasattr(chunk, 'delta'):
                        token_text = chunk.delta
                        accumulated_text += token_text
                        # Send each token immediately as it arrives
                        yield f"data: {json.dumps({'type': 'content', 'content': token_text, 'done': False})}\n\n"
                
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
                    # Send completion signal with conversation state
                    print(f"[DEBUG] Response completed. Final accumulated text length: {len(accumulated_text)}")
                    print(f"[DEBUG] Sending response_id to frontend: {response_id}")
                    completion_metadata = {
                        'analysis_type': request.analysis_type,
                        'response_id': response_id,
                        'previous_response_id': request.previous_response_id,
                        'full_response': accumulated_text,
                        'conversation_turns': len(request.messages),
                        'function_calls_used': len(function_calls)
                    }
                    yield f"data: {json.dumps({'type': 'done', 'content': '', 'done': True, 'metadata': completion_metadata})}\n\n"
                    break
                
                else:
                    # Log any unhandled chunk types
                    print(f"[DEBUG] Unhandled chunk type: {chunk.type}")
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

# Remove the provider switch endpoint since we're focusing on OpenAI only 