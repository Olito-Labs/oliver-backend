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
    """Create system prompt based on analysis type with banking advisor specialization."""
    
    if analysis_type == "compliance":
        return """You are Oliver, a senior-partner banking-risk advisor and primary intake at Olito Labs. Your job is to intake new risk consulting inquiries from banks and confirm all context to set up the case for internal handoff. 

Carefully elicit, summarize, and confirm the following in a focused, structured way, maintaining a highly professional, concise, evidence-based style.

**Stage 1 – Intake & Context Confirmation**

1. **Elicit Essentials (from the user):**
   - Ask for:
     - The bank name (and holding-company name, if different)
     - Any known counterparty or FinTech partner involved, if applicable
     - The problem, deadline, or objective in the user's own words (you will later map it to an internal workflow category)

2. **Retrieve Bank Demographics (from external sources):**
   - Gather and verify:
     - Charter type (national bank, state member, state non-member, FBO branch, credit union, etc.)
     - Latest total assets (US$), tier (< $10 bn, $10–100 bn, $100–250 bn, > $250 bn), cite the report used (e.g., "$47bn assets, 2024 Q1 Call Report")
     - Primary federal regulator(s) and any clear co-regulators (Fed, OCC, FDIC, CFPB, SEC, state, etc.)

3. **Identify / Suggest Workflow:**
   - Compare the problem the user describes to these internal workflow categories:
     - Marketing-Material Compliance Review
     - Examination Preparation
     - MRA / Enforcement Action Remediation
     - Change-Management Governance
     - New Law / New Regulation Impact Analysis
     - Proposed Rulemaking Comment Analysis
     - Board-Reporting / Risk-Dashboard Preparation
     - Third-Party (FinTech) Risk Assessment
     - Other (when none cleanly fits)
   - If the user hasn't named a workflow, propose the two most plausible options and ask which best fits.

4. **Summarise & Confirm Understanding:**
   - In no more than three precise paragraphs:
     1. Bank demographics paragraph (concise, factual, with cited figures and sources)
     2. Workflow suggestion(s) paragraph (your reasoned suggestion of best-fit workflow[s], based only on user input and bank profile)
     3. Direct, concise request for the user to confirm or correct all contextual details and supply any missing information (e.g., deadlines, counterparties, other relevant points); explicitly prompt for confirmation or correction.

5. **STOP and Await Confirmation:**
   - Do not analyse, interpret, or process documents, regulations, or workflows beyond this intake until the user explicitly confirms details ("Confirmed") or provides corrections.
   - When you receive confirmation, pass validated {bank context, counterparty, chosen workflow} to the corresponding workflow-specific prompt or agent.
   - Always end the hand-off message with:  
     `"Context locked. Handing you to the <workflow-name> module now."`

**Style & Guardrails**
- Mirror the approach of a seasoned Chief Risk Officer: direct, evidence-based, and respectful.
- Write in full sentences and crisp paragraphs—no lists, padding, or jargon. Never expose internal methodology names.
- Clearly cite all quantitative figures and data sources inline.
- If any information is incomplete or ambiguous, call it out plainly and ask targeted follow-up questions.
- Never proceed past Stage 1 until the user gives explicit confirmation.

(REMINDER: Your job is to elicit, summarize, confirm, and then stop. Never move on without explicit confirmation. Always use concise, professional paragraphs and cite data/data sources inline. At handoff, always state "Context locked. Handing you to the <workflow-name> module now.")"""
    
    elif analysis_type == "document":
        return """You are Oliver, an AI assistant specialized in document analysis for financial institutions. 
        Focus on analyzing documents for compliance and regulatory requirements. 
        Provide detailed findings that consider regulatory implications and risk factors."""
    
    else:  # general
        return """You are Oliver, an AI assistant specialized in compliance and regulatory matters for financial institutions. 
        You help with questions about compliance, regulations, risk management, and general business topics.
        Provide helpful and professional responses that maintain context from previous conversation."""

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
    """Streaming chat endpoint using OpenAI Responses API with conversation state."""
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
            
            for chunk in stream:
                # Debug: Log all chunk types we receive
                print(f"[DEBUG] Received chunk type: {chunk.type}")
                
                if chunk.type == "response.created":
                    response_id = chunk.response.id
                    print(f"[DEBUG] OpenAI Response ID created: {response_id}")
                    yield f"data: {json.dumps({'type': 'status', 'content': '🤖 Analyzing your request...', 'done': False})}\n\n"
                
                elif chunk.type == "response.in_progress":
                    yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Thinking...', 'done': False})}\n\n"
                
                elif chunk.type == "response.output_text.delta":
                    # Real-time token streaming - this is the key for true streaming!
                    print(f"[DEBUG] Text delta received: '{chunk.delta}'")
                    if hasattr(chunk, 'delta'):
                        token_text = chunk.delta
                        accumulated_text += token_text
                        # Send each token immediately as it arrives
                        yield f"data: {json.dumps({'type': 'content', 'content': token_text, 'done': False})}\n\n"
                
                elif chunk.type == "response.function_call_arguments.delta":
                    # Stream function call arguments for tool calls like web search
                    print(f"[DEBUG] Function call delta: {chunk.delta}")
                    if hasattr(chunk, 'delta'):
                        # Show that we're building function arguments
                        yield f"data: {json.dumps({'type': 'status', 'content': f'🔍 Building search query...', 'done': False})}\n\n"
                
                elif chunk.type == "response.output_item.added":
                    # New output item (function call or text) started
                    print(f"[DEBUG] Output item added: {getattr(chunk, 'item', 'unknown')}")
                    if hasattr(chunk, 'item'):
                        if hasattr(chunk.item, 'type') and chunk.item.type == "function_call":
                            tool_name = getattr(chunk.item, 'name', 'unknown')
                            yield f"data: {json.dumps({'type': 'status', 'content': f'🛠️ Calling {tool_name}...', 'done': False})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'content': '📝 Writing response...', 'done': False})}\n\n"
                
                elif chunk.type == "response.function_call_arguments.done":
                    # Function call arguments complete
                    print(f"[DEBUG] Function call arguments done")
                    yield f"data: {json.dumps({'type': 'status', 'content': '⚡ Executing search...', 'done': False})}\n\n"
                
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
                
                elif chunk.type == "response.output_item.done":
                    # Output item complete
                    print(f"[DEBUG] Output item done")
                    yield f"data: {json.dumps({'type': 'status', 'content': '✅ Response complete', 'done': False})}\n\n"
                
                elif chunk.type == "response.completed":
                    # Send completion signal with conversation state
                    print(f"[DEBUG] Response completed. Final accumulated text length: {len(accumulated_text)}")
                    print(f"[DEBUG] Sending response_id to frontend: {response_id}")
                    completion_metadata = {
                        'analysis_type': request.analysis_type,
                        'response_id': response_id,
                        'previous_response_id': request.previous_response_id,
                        'full_response': accumulated_text,
                        'conversation_turns': len(request.messages)
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