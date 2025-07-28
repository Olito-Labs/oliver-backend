from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, List, Dict, Any, Optional
import json
import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.api import ChatRequest, ChatResponse, ChatMessage, StreamChunk
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api", tags=["chat"])

# Structured Output Models for Banking Compliance
class BankingInstitution(BaseModel):
    name: str
    charter_type: str
    asset_size: str
    asset_size_source: str
    primary_regulators: List[str]
    holding_company: Optional[str] = None

class ComplianceIssue(BaseModel):
    description: str
    urgency: str  # "low", "medium", "high", "critical"
    deadline: Optional[str] = None
    regulatory_context: Optional[str] = None

class WorkflowRecommendation(BaseModel):
    primary_workflow: str
    confidence: str  # "low", "medium", "high"
    reasoning: str
    alternative_workflows: List[str]

class IntakeResponse(BaseModel):
    message_type: str  # "intake_confirmation", "non_banking_redirect", "information_request"
    institution: Optional[BankingInstitution] = None
    issue: Optional[ComplianceIssue] = None
    workflow: Optional[WorkflowRecommendation] = None
    next_steps: List[str]
    requires_confirmation: bool
    response_text: str  # Human-readable response for display

class ComplianceAnalysis(BaseModel):
    summary: str
    key_findings: List[str]
    regulatory_implications: List[str]
    risk_assessment: str  # "low", "medium", "high", "critical"
    recommendations: List[str]
    timeline: Optional[str] = None
    response_text: str  # Human-readable response for display

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
    """Create system prompt optimized for structured outputs."""
    
    return """You are Oliver, a regulatory risk management agent currently focusing on banking institutions.

Your responses must be structured and include both machine-readable data and human-readable text.

**CRITICAL FIRST STEP - Industry & Institution Validation:**

1. **Determine if this is a banking inquiry:** Commercial banks, credit unions, savings associations, bank holding companies, etc.

2. **If NOT banking/financial institutions:** 
   - Set message_type to "non_banking_redirect"
   - Provide polite redirect in response_text
   - Include next_steps for contacting about banking questions

3. **If IS banking institutions:**
   - Set message_type to "intake_confirmation" or "information_request"
   - Gather/confirm institution details (name, charter, assets, regulators)
   - Understand the compliance issue (problem, urgency, deadline)
   - Classify the workflow from these options:
     * Marketing Material Compliance Review
     * Examination Preparation
     * MRA / Enforcement Action Remediation  
     * Change Management Governance
     * New Law/Regulation Impact Analysis
     * Proposed Rulemaking Comment Analysis
     * Board Reporting / Risk Dashboard Preparation
     * Third-Party (FinTech) Risk Assessment
     * Other

**Response Structure Requirements:**
- Always provide a clear, professional response_text for display
- Include structured data for institution, issue, and workflow when applicable
- Set requires_confirmation=true when waiting for user confirmation
- Include specific next_steps for the user
- Use evidence-based language and cite data sources
- Maintain professional banking advisor tone

**Style:** Professional, concise, evidence-based. Always include both structured data and readable text."""
    


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
        
        # Build request parameters with structured outputs
        request_params = {
            "model": settings.OPENAI_MODEL,
            "input": openai_messages,
            "instructions": system_prompt,
            "max_output_tokens": settings.MAX_TOKENS,
            "temperature": settings.TEMPERATURE,
            "tools": tools,
            "stream": False,
            "store": True,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "compliance_intake_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "message_type": {
                                "type": "string",
                                "enum": ["intake_confirmation", "non_banking_redirect", "information_request"]
                            },
                            "institution": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "charter_type": {"type": "string"},
                                    "asset_size": {"type": "string"},
                                    "asset_size_source": {"type": "string"},
                                    "primary_regulators": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "holding_company": {"type": ["string", "null"]}
                                },
                                                                 "required": ["name", "charter_type", "asset_size", "asset_size_source", "primary_regulators", "holding_company"],
                                "additionalProperties": False
                            },
                            "issue": {
                                "type": "object", 
                                "properties": {
                                    "description": {"type": "string"},
                                    "urgency": {
                                        "type": "string",
                                        "enum": ["low", "medium", "high", "critical"]
                                    },
                                    "deadline": {"type": ["string", "null"]},
                                    "regulatory_context": {"type": ["string", "null"]}
                                },
                                                                 "required": ["description", "urgency", "deadline", "regulatory_context"],
                                "additionalProperties": False
                            },
                            "workflow": {
                                "type": "object",
                                "properties": {
                                    "primary_workflow": {"type": "string"},
                                    "confidence": {
                                        "type": "string", 
                                        "enum": ["low", "medium", "high"]
                                    },
                                    "reasoning": {"type": "string"},
                                    "alternative_workflows": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": ["primary_workflow", "confidence", "reasoning", "alternative_workflows"],
                                "additionalProperties": False
                            },
                            "next_steps": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "requires_confirmation": {"type": "boolean"},
                            "response_text": {"type": "string"}
                        },
                        "required": ["message_type", "next_steps", "requires_confirmation", "response_text"],
                        "additionalProperties": False
                    }
                }
            },
            "reasoning": {}
        }
        
        # Critical: Include previous_response_id for conversation state
        if request.previous_response_id:
            request_params["previous_response_id"] = request.previous_response_id
        
        # Call OpenAI Responses API
        response = client.responses.create(**request_params)
        
        # Extract structured response
        response_text = ""
        structured_data = None
        
        if response.output and len(response.output) > 0:
            message_output = response.output[0]
            if hasattr(message_output, 'content') and len(message_output.content) > 0:
                raw_response = message_output.content[0].text
                try:
                    # Parse structured JSON response
                    structured_data = json.loads(raw_response)
                    response_text = structured_data.get('response_text', raw_response)
                except json.JSONDecodeError:
                    # Fallback to raw response if not valid JSON
                    response_text = raw_response
        
        # Create assistant response with structured metadata
        assistant_message = ChatMessage(
            id=str(uuid.uuid4()),
            content=response_text,
            sender="assistant",
            timestamp=datetime.now(),
            metadata={
                "analysis_type": request.analysis_type,
                "response_id": response.id,
                "previous_response_id": request.previous_response_id,
                "structured_data": structured_data  # Include structured response data
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
            
            # Build request parameters with structured outputs
            request_params = {
                "model": settings.OPENAI_MODEL,
                "input": openai_messages,
                "instructions": system_prompt,
                "max_output_tokens": settings.MAX_TOKENS,
                "temperature": settings.TEMPERATURE,
                "tools": tools,
                "stream": True,
                "store": True,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "compliance_intake_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "message_type": {
                                    "type": "string",
                                    "enum": ["intake_confirmation", "non_banking_redirect", "information_request"]
                                },
                                "institution": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "charter_type": {"type": "string"},
                                        "asset_size": {"type": "string"},
                                        "asset_size_source": {"type": "string"},
                                        "primary_regulators": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "holding_company": {"type": ["string", "null"]}
                                    },
                                    "required": ["name", "charter_type", "asset_size", "asset_size_source", "primary_regulators", "holding_company"],
                                    "additionalProperties": False
                                },
                                "issue": {
                                    "type": "object", 
                                    "properties": {
                                        "description": {"type": "string"},
                                        "urgency": {
                                            "type": "string",
                                            "enum": ["low", "medium", "high", "critical"]
                                        },
                                        "deadline": {"type": ["string", "null"]},
                                        "regulatory_context": {"type": ["string", "null"]}
                                    },
                                    "required": ["description", "urgency", "deadline", "regulatory_context"],
                                    "additionalProperties": False
                                },
                                "workflow": {
                                    "type": "object",
                                    "properties": {
                                        "primary_workflow": {"type": "string"},
                                        "confidence": {
                                            "type": "string", 
                                            "enum": ["low", "medium", "high"]
                                        },
                                        "reasoning": {"type": "string"},
                                        "alternative_workflows": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    },
                                    "required": ["primary_workflow", "confidence", "reasoning", "alternative_workflows"],
                                    "additionalProperties": False
                                },
                                "next_steps": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "requires_confirmation": {"type": "boolean"},
                                "response_text": {"type": "string"}
                            },
                            "required": ["message_type", "next_steps", "requires_confirmation", "response_text"],
                            "additionalProperties": False
                        }
                    }
                },
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
                    # Real-time token streaming for structured JSON
                    print(f"[DEBUG] Text delta received: '{chunk.delta}'")
                    if hasattr(chunk, 'delta'):
                        token_text = chunk.delta
                        accumulated_text += token_text
                        # Try to parse accumulated JSON and extract response_text for display
                        try:
                            # Attempt to parse the accumulated JSON
                            json_data = json.loads(accumulated_text)
                            if 'response_text' in json_data:
                                # Send the response_text for live display
                                display_text = json_data['response_text']
                                yield f"data: {json.dumps({'type': 'content', 'content': display_text, 'done': False})}\n\n"
                            else:
                                # If no response_text yet, send a status update
                                yield f"data: {json.dumps({'type': 'status', 'content': '📝 Structuring response...', 'done': False})}\n\n"
                        except json.JSONDecodeError:
                            # JSON not complete yet, send status
                            yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Processing...', 'done': False})}\n\n"
                
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
                    # Send completion signal with structured data
                    print(f"[DEBUG] Response completed. Final accumulated text length: {len(accumulated_text)}")
                    print(f"[DEBUG] Sending response_id to frontend: {response_id}")
                    
                    # Parse the final structured response
                    try:
                        structured_data = json.loads(accumulated_text)
                        completion_metadata = {
                            'analysis_type': request.analysis_type,
                            'response_id': response_id,
                            'previous_response_id': request.previous_response_id,
                            'full_response': structured_data.get('response_text', ''),
                            'structured_data': structured_data,  # Include full structured response
                            'conversation_turns': len(request.messages)
                        }
                        
                        # Send the final response_text as content
                        final_content = structured_data.get('response_text', accumulated_text)
                        yield f"data: {json.dumps({'type': 'content', 'content': final_content, 'done': False})}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'content': '', 'done': True, 'metadata': completion_metadata})}\n\n"
                    except json.JSONDecodeError:
                        # Fallback for non-JSON response
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