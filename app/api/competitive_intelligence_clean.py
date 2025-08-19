from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import json
import asyncio
from datetime import datetime
import uuid

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api/competitive-intelligence", tags=["competitive-intelligence"])

class CompetitiveIntelligenceRequest(BaseModel):
    query: str
    template: Optional[str] = "general"

@router.post("/analyze/stream")
async def stream_competitive_intelligence(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    Stream competitive intelligence analysis using GPT-5 with minimal reasoning.
    Returns real-time streaming output for lightning-fast experience.
    """
    
    async def generate_analysis_stream() -> AsyncGenerator[str, None]:
        try:
            # Send connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"
            
            client = openai_manager.get_client()
            if not client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Analysis service unavailable'})}\n\n"
                return

            # Build template-specific system prompt
            if request.template == "threats":
                system_prompt = """You are Oliver, a senior competitive intelligence analyst for Fulton Bank. 
                Analyze competitive threats in the banking sector. Focus on immediate and emerging threats 
                that could impact Fulton Bank's market position. Provide specific, actionable insights."""
                
            elif request.template == "performance":
                system_prompt = """You are Oliver, a senior competitive intelligence analyst for Fulton Bank.
                Analyze competitive performance metrics and market positioning. Focus on financial performance,
                market share, and operational efficiency comparisons. Provide data-driven insights."""
                
            elif request.template == "strategy":
                system_prompt = """You are Oliver, a senior competitive intelligence analyst for Fulton Bank.
                Analyze competitive strategies and strategic positioning. Focus on business strategy,
                product innovation, and market expansion plans. Provide strategic recommendations."""
                
            else:  # general
                system_prompt = """You are Oliver, a senior competitive intelligence analyst for Fulton Bank.
                Provide comprehensive competitive intelligence analysis. Focus on strategic insights
                that would be valuable for executive decision-making."""

            # Configure GPT-5 with minimal reasoning for speed and streaming
            request_params = {
                "model": settings.OPENAI_MODEL,
                "input": request.query,
                "instructions": system_prompt,
                "max_output_tokens": 5000,
                "stream": True,  # Enable streaming
                "store": True
            }
            
            # Use minimal reasoning effort for lightning-fast responses
            if settings.OPENAI_MODEL.startswith("gpt-5"):
                request_params["reasoning"] = {"effort": "minimal"}  # Fastest reasoning
                request_params["text"] = {"verbosity": "medium"}     # Balanced output
                print(f"[CI] Using GPT-5 with minimal reasoning effort for speed")
            elif settings.OPENAI_MODEL.startswith("o3"):
                request_params["reasoning"] = {"effort": "low", "summary": "auto"}
            else:
                request_params["temperature"] = 0.7

            # Start streaming analysis
            print(f"[CI] Starting streaming competitive intelligence analysis")
            yield f"data: {json.dumps({'type': 'analysis_start', 'message': 'Oliver is analyzing...'})}\n\n"
            
            response = client.responses.create(**request_params)
            
            # Process streaming response with comprehensive debugging
            full_content = ""
            chunk_count = 0
            
            print(f"[CI] Starting to process streaming response...")
            
            for chunk in response:
                chunk_count += 1
                print(f"[CI] Processing chunk {chunk_count}")
                print(f"[CI] Chunk type: {type(chunk)}")
                print(f"[CI] Chunk attributes: {[attr for attr in dir(chunk) if not attr.startswith('_')]}")
                
                if hasattr(chunk, 'output') and chunk.output:
                    print(f"[CI] Chunk has output with {len(chunk.output)} items")
                    for i, item in enumerate(chunk.output):
                        print(f"[CI] Output item {i} type: {getattr(item, 'type', 'unknown')}")
                        
                        if hasattr(item, 'type') and item.type == 'message':
                            print(f"[CI] Found message item")
                            if hasattr(item, 'content') and item.content:
                                print(f"[CI] Message has {len(item.content)} content items")
                                for j, content_item in enumerate(item.content):
                                    print(f"[CI] Content item {j} type: {getattr(content_item, 'type', 'unknown')}")
                                    print(f"[CI] Content item attributes: {[attr for attr in dir(content_item) if not attr.startswith('_')]}")
                                    
                                    if hasattr(content_item, 'text'):
                                        content_chunk = content_item.text
                                        full_content += content_chunk
                                        print(f"[CI] Got content chunk: {len(content_chunk)} chars - {content_chunk[:100]}...")
                                        
                                        # Stream content as it's generated
                                        yield f"data: {json.dumps({'type': 'content', 'content': content_chunk})}\n\n"
                                        await asyncio.sleep(0.01)
                else:
                    print(f"[CI] Chunk has no output attribute")

            print(f"[CI] Processed {chunk_count} chunks, total content: {len(full_content)} chars")

            # If no streaming content, try to get final output
            if not full_content:
                print(f"[CI] No streaming content found, trying final output...")
                
                if hasattr(response, 'output_text') and response.output_text:
                    full_content = response.output_text
                    print(f"[CI] Got content from output_text: {len(full_content)} chars")
                    yield f"data: {json.dumps({'type': 'content', 'content': full_content})}\n\n"
                    
                elif hasattr(response, 'output') and response.output:
                    print(f"[CI] Checking final response.output with {len(response.output)} items")
                    for item in response.output:
                        print(f"[CI] Final output item type: {getattr(item, 'type', 'unknown')}")
                        if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                            for c in item.content:
                                print(f"[CI] Final content item type: {getattr(c, 'type', 'unknown')}")
                                if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                    full_content = c.text
                                    print(f"[CI] Got final content: {len(full_content)} chars")
                                    yield f"data: {json.dumps({'type': 'content', 'content': full_content})}\n\n"
                                    break
                else:
                    print(f"[CI] Response has no output attribute")
                    print(f"[CI] Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")

            if not full_content:
                print(f"[CI] ERROR: Still no content found after all attempts")
                yield f"data: {json.dumps({'type': 'error', 'message': 'No content generated - check backend logs'})}\n\n"
                return

            print(f"[CI] Generated {len(full_content)} characters of analysis")

            # Store the analysis
            try:
                analysis_record = {
                    'id': str(uuid.uuid4()),
                    'user_id': user['uid'],
                    'query': request.query,
                    'template': request.template,
                    'analysis_content': full_content,
                    'metadata': {
                        "model_used": settings.OPENAI_MODEL,
                        "template": request.template,
                        "content_length": len(full_content),
                        "reasoning_effort": "minimal"
                    },
                    'created_at': datetime.utcnow().isoformat()
                }
                
                result = supabase.table('competitive_intelligence_analyses').insert(analysis_record).execute()
                analysis_id = result.data[0]['id'] if result.data else None
                
                # Send completion
                yield f"data: {json.dumps({'type': 'complete', 'analysis_id': analysis_id})}\n\n"
                
            except Exception as storage_error:
                print(f"Failed to store analysis: {storage_error}")
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            error_message = f"Analysis failed: {str(e)}"
            print(f"[CI] Error: {error_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
    
    return StreamingResponse(
        generate_analysis_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.get("/templates")
async def get_analysis_templates():
    """Get available analysis templates"""
    templates = [
        {
            "id": "threats",
            "title": "Competitive Threats Analysis",
            "description": "Analyze immediate and emerging competitive threats"
        },
        {
            "id": "performance", 
            "title": "Performance Benchmarking",
            "description": "Compare financial and operational performance metrics"
        },
        {
            "id": "strategy",
            "title": "Strategic Positioning Analysis", 
            "description": "Analyze competitive strategies and market positioning"
        }
    ]
    
    return {"templates": templates}
