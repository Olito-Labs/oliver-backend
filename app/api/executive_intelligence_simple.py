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

router = APIRouter(prefix="/api/executive-intelligence-simple", tags=["executive-intelligence-simple"])

class ExecutiveBriefingRequest(BaseModel):
    strategic_focus: str
    executive_context: Optional[str] = "CEO of Fulton Bank"
    urgency: Optional[str] = "standard"

@router.post("/briefing/stream")
async def stream_simple_executive_briefing(
    request: ExecutiveBriefingRequest,
    user=Depends(get_current_user)
):
    """
    Simple, reliable executive briefing with guaranteed streaming.
    Uses direct GPT-5 calls for lightning-fast experience.
    """
    
    async def generate_simple_stream() -> AsyncGenerator[str, None]:
        try:
            # Send connection confirmation
            yield "data: {\"type\": \"connected\", \"message\": \"Oliver is preparing your briefing\"}\n\n"
            await asyncio.sleep(0.5)
            
            # Send document structure immediately
            structure = {
                "type": "structure",
                "sections": [
                    {"id": "executive_takeaways", "title": "1.0 Executive Takeaways", "status": "pending"},
                    {"id": "competitive_analysis", "title": "2.0 Competitive Analysis", "status": "pending"},
                    {"id": "strategic_implications", "title": "3.0 Strategic Implications", "status": "pending"},
                    {"id": "recommendations", "title": "4.0 Recommendations", "status": "pending"}
                ]
            }
            yield f"data: {json.dumps(structure)}\n\n"
            await asyncio.sleep(0.5)

            # Get OpenAI client
            client = openai_manager.get_client()
            if not client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Analysis service unavailable'})}\n\n"
                return

            # Simple, focused system prompt
            system_prompt = f"""
You are Oliver, the elite competitive intelligence analyst for {request.executive_context}.

Analyze: {request.strategic_focus}

Structure your briefing with these exact sections:

## 1.0 Executive Takeaways
Lead with the most critical strategic insights. Focus on implications for Fulton Bank's competitive position.

## 2.0 Competitive Analysis  
Analyze key competitors and their strategic moves relevant to this topic.

## 3.0 Strategic Implications
What does this mean for Fulton Bank's market position and strategic options?

## 4.0 Recommendations
Provide 3-4 specific, actionable recommendations with clear next steps.

Be concise, authoritative, and focus on strategic implications over operational details.
"""

            # Start with Executive Takeaways
            sections = ["executive_takeaways", "competitive_analysis", "strategic_implications", "recommendations"]
            section_prompts = {
                "executive_takeaways": f"Provide executive takeaways for: {request.strategic_focus}. Focus on the most critical strategic insights and implications for Fulton Bank's competitive position. Be concise and authoritative.",
                "competitive_analysis": f"Analyze key competitors relevant to: {request.strategic_focus}. Focus on their strategic moves and competitive positioning.",
                "strategic_implications": f"What are the strategic implications of {request.strategic_focus} for Fulton Bank's market position and strategic options?",
                "recommendations": f"Provide 3-4 specific, actionable recommendations for Fulton Bank regarding: {request.strategic_focus}. Include clear next steps."
            }

            full_content = ""
            
            for section_id in sections:
                # Start section
                yield f"data: {json.dumps({'type': 'section_start', 'section': section_id, 'status': 'Analyzing...'})}\n\n"
                await asyncio.sleep(0.3)

                # Generate section content
                section_prompt = section_prompts[section_id]
                
                # Use responses API for GPT-5 compatibility
                section_params = {
                    "model": settings.OPENAI_MODEL,
                    "input": section_prompt,
                    "instructions": system_prompt,
                    "max_output_tokens": 5000,
                    "stream": True,
                    "store": True
                }
                
                # Add GPT-5 specific parameters
                if settings.OPENAI_MODEL.startswith("gpt-5"):
                    section_params["reasoning"] = {"effort": "medium"}
                    section_params["text"] = {"verbosity": "medium"}
                elif settings.OPENAI_MODEL.startswith("o3"):
                    section_params["reasoning"] = {"effort": "medium", "summary": "detailed"}
                else:
                    section_params["temperature"] = 0.7
                
                response = client.responses.create(**section_params)

                section_content = ""
                section_title = structure["sections"][sections.index(section_id)]["title"]
                
                # Add section header
                section_header = f"\n\n## {section_title}\n\n"
                full_content += section_header
                yield f"data: {json.dumps({'type': 'content_stream', 'content': section_header, 'section': section_id})}\n\n"
                await asyncio.sleep(0.1)

                # Process responses API output - use output_text for simplicity
                section_text = ""
                
                try:
                    print(f"[Executive] Generating section {section_id} with prompt: {section_prompt[:100]}...")
                    
                    # Check if response has output_text (simple access)
                    if hasattr(response, 'output_text') and response.output_text:
                        section_text = response.output_text
                        print(f"[Executive] Got section via output_text: {len(section_text)} chars")
                        
                        # Stream it in chunks for smooth display
                        chunk_size = 30
                        for i in range(0, len(section_text), chunk_size):
                            chunk = section_text[i:i+chunk_size]
                            yield f"data: {json.dumps({'type': 'content_stream', 'content': chunk, 'section': section_id})}\n\n"
                            await asyncio.sleep(0.03)  # Smooth streaming
                    
                    # Fallback: check output array
                    elif hasattr(response, 'output') and response.output:
                        print(f"[Executive] Processing output array for section {section_id}")
                        for item in response.output:
                            print(f"[Executive] Output item type: {getattr(item, 'type', 'unknown')}")
                            if hasattr(item, 'type') and item.type == 'message':
                                if hasattr(item, 'content') and item.content:
                                    for content_item in item.content:
                                        if hasattr(content_item, 'text'):
                                            section_text = content_item.text
                                            print(f"[Executive] Got section content from output array: {len(section_text)} chars")
                                            
                                            # Stream it in chunks
                                            chunk_size = 30
                                            for i in range(0, len(section_text), chunk_size):
                                                chunk = section_text[i:i+chunk_size]
                                                yield f"data: {json.dumps({'type': 'content_stream', 'content': chunk, 'section': section_id})}\n\n"
                                                await asyncio.sleep(0.03)
                                            break
                    else:
                        print(f"[Executive] No content found in response for section {section_id}")
                        print(f"[Executive] Response attributes: {dir(response)}")
                        
                        # Generate fallback content
                        fallback_content = f"*Section content generation in progress for {section_title}...*\n\n"
                        yield f"data: {json.dumps({'type': 'content_stream', 'content': fallback_content, 'section': section_id})}\n\n"
                
                    section_content += section_text
                    full_content += section_text
                    print(f"[Executive] Section {section_id} final length: {len(section_text)} chars")
                    
                except Exception as section_error:
                    print(f"[Executive] Error processing section {section_id}: {section_error}")
                    error_content = f"\n\n*Error generating section {section_title}: {str(section_error)}*\n\n"
                    yield f"data: {json.dumps({'type': 'content_stream', 'content': error_content, 'section': section_id})}\n\n"

                # Complete section
                yield f"data: {json.dumps({'type': 'section_complete', 'section': section_id})}\n\n"
                await asyncio.sleep(0.2)

            # Store the briefing
            try:
                briefing_record = {
                    'id': str(uuid.uuid4()),
                    'user_id': user['uid'],
                    'strategic_focus': request.strategic_focus,
                    'executive_context': request.executive_context,
                    'briefing_content': full_content,
                    'metadata': {
                        "model_used": settings.OPENAI_MODEL,
                        "sections_generated": len(sections),
                        "briefing_length": len(full_content),
                        "approach": "simple_streaming"
                    },
                    'created_at': datetime.utcnow().isoformat()
                }
                
                result = supabase.table('executive_briefings').insert(briefing_record).execute()
                briefing_id = result.data[0]['id'] if result.data else None
                
                print(f"✅ Executive briefing stored: {briefing_id}")
                
                # Send completion
                yield f"data: {json.dumps({'type': 'briefing_complete', 'briefing_id': briefing_id, 'sections': len(sections)})}\n\n"
                
            except Exception as storage_error:
                print(f"❌ Failed to store briefing: {storage_error}")
                # Still complete successfully
                yield f"data: {json.dumps({'type': 'briefing_complete', 'sections': len(sections)})}\n\n"
                
        except Exception as e:
            error_message = f"Executive briefing failed: {str(e)}"
            print(f"❌ Executive briefing error: {error_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
    
    return StreamingResponse(
        generate_simple_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.get("/proactive-briefings")
async def get_simple_proactive_briefings(user=Depends(get_current_user)):
    """Generate simple proactive briefing suggestions"""
    try:
        suggestions = [
            {
                "id": "q4_performance",
                "title": "Q4 Performance vs Regional Competitors",
                "description": "Analyze Q4 competitive positioning and performance metrics",
                "urgency": "standard",
                "estimated_time": "2-3 minutes"
            },
            {
                "id": "digital_banking_threats",
                "title": "Digital Banking Competitive Threats",
                "description": "Assessment of digital transformation initiatives by key competitors",
                "urgency": "urgent",
                "estimated_time": "3-4 minutes"
            },
            {
                "id": "market_share_trends",
                "title": "Regional Market Share Analysis",
                "description": "Current market share trends and competitive dynamics",
                "urgency": "standard",
                "estimated_time": "2-3 minutes"
            },
            {
                "id": "regulatory_compliance",
                "title": "Competitor Regulatory Compliance Strategies",
                "description": "Analysis of how competitors are addressing regulatory changes",
                "urgency": "standard",
                "estimated_time": "3-4 minutes"
            }
        ]
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating suggestions: {str(e)}")
