from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, AsyncGenerator
import json
import asyncio
from datetime import datetime
import uuid

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api/executive-intelligence", tags=["executive-intelligence"])

class ExecutiveBriefingRequest(BaseModel):
    """Request for executive competitive intelligence briefing"""
    strategic_focus: str
    executive_context: Optional[str] = "CEO of Fulton Bank"  # Default context
    urgency: Optional[str] = "standard"  # standard, urgent, deep_dive

class ProactiveBriefingRequest(BaseModel):
    """Request for proactive intelligence suggestions"""
    executive_role: str = "CEO"
    bank_name: str = "Fulton Bank"

@router.post("/briefing/stream")
async def stream_executive_briefing(
    request: ExecutiveBriefingRequest,
    user=Depends(get_current_user)
):
    """
    Stream an executive briefing with live document generation.
    Designed for C-Suite executives who need immediate, actionable intelligence.
    """
    
    async def generate_briefing_stream() -> AsyncGenerator[str, None]:
        try:
            # Send connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"
            
            # Send document structure immediately
            structure = {
                "type": "structure",
                "sections": [
                    {"id": "executive_takeaways", "title": "1.0 Executive Takeaways", "status": "pending"},
                    {"id": "peer_group", "title": "2.0 Peer Group Definition & Methodology", "status": "pending"},
                    {"id": "kpi_comparison", "title": "3.0 Key Performance Indicators (KPI) Comparison", "status": "pending"},
                    {"id": "threat_analysis", "title": "4.0 Strategic Threat Analysis", "status": "pending"},
                    {"id": "recommendations", "title": "5.0 Recommendations for Fulton Bank", "status": "pending"}
                ]
            }
            yield f"data: {json.dumps(structure)}\n\n"
            await asyncio.sleep(0.5)
            
            # Get OpenAI client
            client = openai_manager.get_client()
            if not client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Analysis service unavailable'})}\n\n"
                return

            # Build executive-focused system prompt
            system_prompt = f"""
You are Oliver, the elite competitive intelligence analyst for {request.executive_context}. You are preparing a strategic briefing that will be presented directly to the C-Suite.

Your task: Analyze "{request.strategic_focus}" and prepare a comprehensive intelligence briefing.

Critical Requirements:
1. Write for executives: Focus on strategic implications, not operational details
2. Lead with synthesis: Start with conclusions, then provide supporting evidence
3. Be specific: Include concrete data points, market share figures, financial metrics
4. Identify threats and opportunities: What should the executive be concerned about or excited about?
5. Provide clear recommendations: Specific, actionable next steps

Structure your briefing exactly as follows:

## 1.0 Executive Takeaways
- Start with the most critical strategic insights
- Lead with implications for Fulton Bank's competitive position
- Include 3-4 bullet points with specific, quantifiable impacts

## 2.0 Peer Group Definition & Methodology
- Define the competitive peer group being analyzed
- Brief methodology explanation (1-2 sentences)
- Justify why these competitors are strategically relevant

## 3.0 Key Performance Indicators (KPI) Comparison
- Present data in comparative format
- Focus on metrics that matter for strategic decision-making
- Include market share, growth rates, profitability where available

## 4.0 Strategic Threat Analysis
- Identify immediate and emerging competitive threats
- Assess probability and potential impact
- Focus on threats that could affect next 2-4 quarters

## 5.0 Recommendations for Fulton Bank
- Provide 3-5 specific, actionable recommendations
- Include implementation timeframes where relevant
- Prioritize by strategic importance and feasibility

Use current market data and recent developments. Be authoritative and confident in your analysis.
"""

            # Configure GPT-5 with highest reasoning for executive-quality analysis
            request_params = {
                "model": settings.OPENAI_MODEL,
                "input": f"Prepare a competitive intelligence briefing on: {request.strategic_focus}",
                "instructions": system_prompt,
                "max_output_tokens": 6000,
                "stream": True,
                "store": True,
                "tools": [{"type": "web_search_preview"}]  # Enable web search for current data
            }
            
            # Use highest reasoning effort for executive briefings
            if settings.OPENAI_MODEL.startswith("gpt-5"):
                request_params["reasoning"] = {"effort": "high"}
                request_params["text"] = {"verbosity": "high"}
                print(f"[Executive] Using GPT-5 with high reasoning effort")
            elif settings.OPENAI_MODEL.startswith("o3"):
                request_params["reasoning"] = {"effort": "high", "summary": "detailed"}
            else:
                request_params["temperature"] = 0.7

            # Start analysis with section updates
            current_section = "executive_takeaways"
            yield f"data: {json.dumps({'type': 'section_start', 'section': current_section, 'status': 'Synthesizing findings...'})}\n\n"
            
            # Execute the briefing generation
            response = client.responses.create(**request_params)
            
            # Track metrics
            web_searches = 0
            content_buffer = ""
            current_section_content = ""
            sections_content = {}
            
            # Process streaming response
            for chunk in response:
                if hasattr(chunk, 'output') and chunk.output:
                    for item in chunk.output:
                        if hasattr(item, 'type'):
                            
                            # Handle web search calls
                            if item.type == 'web_search_call':
                                web_searches += 1
                                search_query = ""
                                if hasattr(item, 'action') and item.action:
                                    search_query = item.action.get('query', 'Researching...')
                                
                                # Update current section status
                                yield f"data: {json.dumps({'type': 'section_update', 'section': current_section, 'status': f'Researching: {search_query[:50]}...'})}\n\n"
                                await asyncio.sleep(0.2)
                            
                            # Handle reasoning steps
                            elif item.type == 'reasoning':
                                reasoning_content = ""
                                if hasattr(item, 'summary') and item.summary:
                                    for summary_item in item.summary:
                                        if hasattr(summary_item, 'text'):
                                            reasoning_content = summary_item.text[:100] + "..."
                                            break
                                
                                if reasoning_content:
                                    yield f"data: {json.dumps({'type': 'section_update', 'section': current_section, 'status': f'Analyzing: {reasoning_content}'})}\n\n"
                                    await asyncio.sleep(0.1)
                            
                            # Handle content generation
                            elif item.type == 'message':
                                if hasattr(item, 'content') and item.content:
                                    for content_item in item.content:
                                        if hasattr(content_item, 'text'):
                                            new_content = content_item.text
                                            content_buffer += new_content
                                            
                                            # Detect section changes by looking for section headers
                                            lines = content_buffer.split('\n')
                                            for line in lines:
                                                if line.startswith('## 1.0 Executive Takeaways'):
                                                    current_section = "executive_takeaways"
                                                    yield f"data: {json.dumps({'type': 'section_start', 'section': current_section, 'status': 'Writing executive summary...'})}\n\n"
                                                elif line.startswith('## 2.0 Peer Group'):
                                                    # Complete previous section
                                                    yield f"data: {json.dumps({'type': 'section_complete', 'section': 'executive_takeaways'})}\n\n"
                                                    current_section = "peer_group"
                                                    yield f"data: {json.dumps({'type': 'section_start', 'section': current_section, 'status': 'Defining competitive peer group...'})}\n\n"
                                                elif line.startswith('## 3.0 Key Performance'):
                                                    yield f"data: {json.dumps({'type': 'section_complete', 'section': 'peer_group'})}\n\n"
                                                    current_section = "kpi_comparison"
                                                    yield f"data: {json.dumps({'type': 'section_start', 'section': current_section, 'status': 'Analyzing performance metrics...'})}\n\n"
                                                elif line.startswith('## 4.0 Strategic Threat'):
                                                    yield f"data: {json.dumps({'type': 'section_complete', 'section': 'kpi_comparison'})}\n\n"
                                                    current_section = "threat_analysis"
                                                    yield f"data: {json.dumps({'type': 'section_start', 'section': current_section, 'status': 'Assessing competitive threats...'})}\n\n"
                                                elif line.startswith('## 5.0 Recommendations'):
                                                    yield f"data: {json.dumps({'type': 'section_complete', 'section': 'threat_analysis'})}\n\n"
                                                    current_section = "recommendations"
                                                    yield f"data: {json.dumps({'type': 'section_start', 'section': current_section, 'status': 'Formulating strategic recommendations...'})}\n\n"
                                            
                                            # Stream content as it's generated
                                            yield f"data: {json.dumps({'type': 'content_stream', 'content': new_content, 'section': current_section})}\n\n"
                                            await asyncio.sleep(0.05)  # Smooth streaming
            
            # Complete the final section
            yield f"data: {json.dumps({'type': 'section_complete', 'section': current_section})}\n\n"
            
            # Store the briefing
            try:
                briefing_record = {
                    'id': str(uuid.uuid4()),
                    'user_id': user['uid'],
                    'strategic_focus': request.strategic_focus,
                    'executive_context': request.executive_context,
                    'briefing_content': content_buffer,
                    'metadata': {
                        "web_searches": web_searches,
                        "model_used": settings.OPENAI_MODEL,
                        "urgency": request.urgency,
                        "briefing_length": len(content_buffer)
                    },
                    'created_at': datetime.utcnow().isoformat()
                }
                
                result = supabase.table('executive_briefings').insert(briefing_record).execute()
                briefing_id = result.data[0]['id'] if result.data else None
                
                # Send completion
                yield f"data: {json.dumps({'type': 'briefing_complete', 'briefing_id': briefing_id, 'web_searches': web_searches})}\n\n"
                
            except Exception as storage_error:
                print(f"Failed to store briefing: {storage_error}")
                yield f"data: {json.dumps({'type': 'briefing_complete', 'web_searches': web_searches})}\n\n"
                
        except Exception as e:
            error_message = f"Briefing generation failed: {str(e)}"
            print(f"[Executive] Error: {error_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
    
    return StreamingResponse(
        generate_briefing_stream(),
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
async def get_proactive_briefings(user=Depends(get_current_user)):
    """
    Generate proactive briefing suggestions based on current market conditions
    and the executive's likely strategic concerns.
    """
    try:
        # These would be dynamically generated based on:
        # - Recent market events
        # - The user's bank context
        # - Seasonal/quarterly reporting cycles
        # - Previous briefing history
        
        suggestions = [
            {
                "id": "q4_market_share",
                "title": "Q4 Performance & Market Share Analysis",
                "description": "Comprehensive analysis of Q4 competitive positioning and market share trends",
                "urgency": "standard",
                "estimated_time": "3-5 minutes"
            },
            {
                "id": "fintech_merger_threat",
                "title": "Threat Assessment: Recent Regional Fintech Merger",
                "description": "Impact analysis of the latest fintech consolidation on regional banking",
                "urgency": "urgent",
                "estimated_time": "2-3 minutes"
            },
            {
                "id": "competitor_earnings_analysis",
                "title": "Competitor Earnings Call Analysis",
                "description": "Strategic insights from recent competitor investor relations transcripts",
                "urgency": "standard",
                "estimated_time": "4-6 minutes"
            },
            {
                "id": "digital_banking_trends",
                "title": "Digital Banking Innovation Landscape",
                "description": "Analysis of digital transformation initiatives across peer institutions",
                "urgency": "standard",
                "estimated_time": "5-7 minutes"
            }
        ]
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating suggestions: {str(e)}")

@router.get("/briefings")
async def list_executive_briefings(user=Depends(get_current_user)):
    """List recent executive briefings"""
    try:
        result = supabase.table('executive_briefings')\
            .select("id, strategic_focus, executive_context, created_at, metadata")\
            .eq('user_id', user['uid'])\
            .order('created_at', desc=True)\
            .limit(20)\
            .execute()
        
        return {"briefings": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching briefings: {str(e)}")

@router.get("/briefings/{briefing_id}")
async def get_executive_briefing(briefing_id: str, user=Depends(get_current_user)):
    """Get a specific executive briefing"""
    try:
        result = supabase.table('executive_briefings')\
            .select("*")\
            .eq('id', briefing_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Briefing not found")
        
        return {"briefing": result.data}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Briefing not found")
        raise HTTPException(status_code=500, detail=f"Error fetching briefing: {str(e)}")

@router.post("/contextual-analysis")
async def contextual_analysis(
    payload: Dict[str, Any],
    user=Depends(get_current_user)
):
    """
    Perform contextual analysis on a specific piece of content.
    Used when executives click on insights for deeper analysis.
    """
    try:
        selected_text = payload.get('selected_text', '')
        analysis_type = payload.get('analysis_type', 'expand')  # expand, verify, challenge, pivot
        context = payload.get('context', '')
        
        if not selected_text:
            raise HTTPException(status_code=400, detail="No text selected for analysis")

        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="Analysis service unavailable")

        # Build contextual analysis prompt
        if analysis_type == 'expand':
            analysis_prompt = f"Provide deeper analysis and additional context for this insight: '{selected_text}'. Include specific data points and strategic implications."
        elif analysis_type == 'verify':
            analysis_prompt = f"Verify this claim and provide supporting evidence: '{selected_text}'. Include sources and confidence assessment."
        elif analysis_type == 'challenge':
            analysis_prompt = f"Challenge this assertion and provide alternative perspectives: '{selected_text}'. Look for contradictory evidence or different interpretations."
        elif analysis_type == 'pivot':
            analysis_prompt = f"Use this insight as a starting point for related strategic analysis: '{selected_text}'. What adjacent opportunities or risks should be considered?"
        else:
            analysis_prompt = f"Analyze this statement in more detail: '{selected_text}'"

        # Execute contextual analysis
        request_params = {
            "model": settings.OPENAI_MODEL,
            "input": analysis_prompt,
            "instructions": f"You are Oliver, providing executive-level contextual analysis. Context: {context}",
            "max_output_tokens": 1500,
            "tools": [{"type": "web_search_preview"}]
        }
        
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            request_params["reasoning"] = {"effort": "medium"}
            request_params["text"] = {"verbosity": "medium"}

        response = client.responses.create(**request_params)
        
        # Extract content
        analysis_content = ""
        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if item.type == 'message' and hasattr(item, 'content'):
                    for content_item in item.content:
                        if hasattr(content_item, 'text'):
                            analysis_content = content_item.text
                            break

        return {
            "analysis": analysis_content,
            "analysis_type": analysis_type,
            "selected_text": selected_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contextual analysis failed: {str(e)}")
