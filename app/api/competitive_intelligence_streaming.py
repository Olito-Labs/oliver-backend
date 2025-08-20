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
    Lightning-fast streaming for real-time experience.
    """
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Send connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"
            
            client = openai_manager.get_client()
            if not client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'OpenAI client unavailable'})}\n\n"
                return

            # Simple system prompt
            system_prompt = f"""You are Oliver, a competitive intelligence analyst for Fulton Bank. 
            Analyze the following query and provide strategic insights: {request.query}"""

            print(f"[CI-Stream] Starting streaming analysis: {request.query[:100]}...")

            # GPT-5 with minimal reasoning and streaming
            response = client.responses.create(
                model=settings.OPENAI_MODEL,
                input=request.query,
                instructions=system_prompt,
                reasoning={"effort": "minimal"},  # Lightning fast
                text={"verbosity": "medium"},
                max_output_tokens=3000,
                stream=True  # Enable streaming
            )

            print(f"[CI-Stream] Processing streaming response...")
            
            full_content = ""
            chunk_count = 0
            
            # Process streaming chunks using the correct ResponseTextDeltaEvent format
            for chunk in response:
                chunk_count += 1
                
                # Handle ResponseTextDeltaEvent with delta.text (correct format from your logs)
                if hasattr(chunk, 'delta') and chunk.delta and hasattr(chunk.delta, 'text'):
                    content_chunk = chunk.delta.text
                    full_content += content_chunk
                    
                    # Stream content immediately
                    yield f"data: {json.dumps({'type': 'content', 'content': content_chunk})}\n\n"
                    
                    # Log progress every 500 chunks
                    if chunk_count % 500 == 0:
                        print(f"[CI-Stream] Processed {chunk_count} chunks, {len(full_content)} chars so far...")

            print(f"[CI-Stream] Streaming complete: {chunk_count} chunks, {len(full_content)} total chars")

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
                        "reasoning_effort": "minimal",
                        "chunks_processed": chunk_count,
                        "content_length": len(full_content),
                        "streaming": True
                    },
                    'created_at': datetime.utcnow().isoformat()
                }
                
                result = supabase.table('competitive_intelligence_analyses').insert(analysis_record).execute()
                analysis_id = result.data[0]['id'] if result.data else None
                
                yield f"data: {json.dumps({'type': 'complete', 'analysis_id': analysis_id, 'total_chunks': chunk_count})}\n\n"
                
            except Exception as storage_error:
                print(f"[CI-Stream] Storage failed: {storage_error}")
                yield f"data: {json.dumps({'type': 'complete', 'total_chunks': chunk_count})}\n\n"

        except Exception as e:
            error_message = f"Streaming analysis failed: {str(e)}"
            print(f"[CI-Stream] ERROR: {error_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
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
async def get_streaming_templates():
    """Get analysis templates for streaming"""
    return {
        "templates": [
            {
                "id": "threats",
                "title": "Competitive Threats",
                "query": "Analyze current competitive threats facing Fulton Bank in digital banking and fintech competition"
            },
            {
                "id": "performance", 
                "title": "Performance Analysis",
                "query": "Compare Fulton Bank's financial performance and market position against regional competitors"
            },
            {
                "id": "strategy",
                "title": "Strategic Opportunities",
                "query": "Identify strategic opportunities and market positioning advantages for Fulton Bank"
            }
        ]
    }
