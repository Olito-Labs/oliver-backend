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

router = APIRouter(prefix="/api/competitive-intelligence", tags=["competitive-intelligence"])

class CompetitiveIntelligenceRequest(BaseModel):
    """Request model for competitive intelligence research"""
    research_query: str
    competitors: Optional[List[str]] = None
    focus_areas: Optional[List[str]] = None
    time_horizon: Optional[str] = "last 12 months"
    depth: Optional[str] = "standard"  # quick, standard, comprehensive
    include_financials: bool = True
    include_products: bool = True
    include_strategy: bool = True
    include_regulatory: bool = True

@router.post("/research/stream")
async def stream_competitive_intelligence_research(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    Stream competitive intelligence research using GPT-5 with reasoning and web search.
    Returns real-time thinking process and structured analysis.
    """
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"
            
            # Build comprehensive system prompt for competitive intelligence
            system_prompt = f"""
You are Oliver, a senior competitive intelligence analyst for a global financial institution. Your task is to conduct comprehensive research and analysis on the competitive landscape in banking and financial services.

Research Parameters:
- Primary Query: {request.research_query}
- Target Competitors: {', '.join(request.competitors) if request.competitors else 'Identify and analyze key competitors in the banking sector'}
- Analysis Time Horizon: {request.time_horizon}
- Research Depth: {request.depth}
- Focus Areas: {', '.join(request.focus_areas) if request.focus_areas else 'All relevant competitive factors'}

Analysis Requirements:
{'- Financial Performance Analysis: Revenue trends, profitability metrics, market capitalization, key financial ratios' if request.include_financials else ''}
{'- Product Strategy Assessment: Product portfolios, innovation pipelines, digital transformation initiatives' if request.include_products else ''}
{'- Strategic Positioning Review: Market positioning, M&A activity, partnerships, expansion strategies' if request.include_strategy else ''}
{'- Regulatory Compliance Analysis: Regulatory issues, compliance track record, risk management approaches' if request.include_regulatory else ''}

Research Methodology:
1. Use web search to gather the most current information about competitors and market conditions
2. Focus on recent developments, earnings reports, strategic announcements, and market analysis
3. Analyze competitive advantages, vulnerabilities, and strategic positioning
4. Identify emerging trends, opportunities, and threats
5. Synthesize findings into actionable strategic recommendations

Output Format:
Structure your analysis as a comprehensive competitive intelligence report with:
- Executive Summary (key findings and strategic implications)
- Competitive Landscape Overview (market structure and dynamics)
- Individual Competitor Analysis (detailed profiles with strengths/weaknesses)
- Market Trends and Emerging Patterns
- Strategic Opportunities and Threat Assessment
- Actionable Recommendations with Implementation Priorities

Requirements:
- Include specific data points, metrics, and quantitative analysis where available
- Provide source citations for key claims and data
- Focus on actionable insights that inform strategic decision-making
- Maintain professional tone suitable for executive presentation
- Use clear headings and structured formatting for easy navigation

Begin your research and analysis now.
"""

            # Get OpenAI client
            client = openai_manager.get_client()
            if not client:
                yield f"data: {json.dumps({'type': 'error', 'message': 'OpenAI client not available'})}\n\n"
                return

            # Configure GPT-5 with reasoning and web search
            request_params = {
                "model": settings.OPENAI_MODEL,  # Should be gpt-5
                "input": request.research_query,
                "instructions": system_prompt,
                "max_output_tokens": 8000,
                "stream": True,  # Enable streaming for real-time thinking
                "store": True,   # Store for debugging
                "tools": [
                    {
                        "type": "web_search_preview"  # Enable web search
                    }
                ]
            }
            
            # Add GPT-5 specific parameters for highest quality thinking
            if settings.OPENAI_MODEL.startswith("gpt-5"):
                request_params["reasoning"] = {
                    "effort": "high"  # Highest reasoning effort for comprehensive analysis
                }
                request_params["text"] = {
                    "verbosity": "high"  # Detailed explanations
                }
                print(f"[CI] Using GPT-5 with high reasoning effort for competitive intelligence")
            elif settings.OPENAI_MODEL.startswith("o3"):
                request_params["reasoning"] = {
                    "effort": "high",
                    "summary": "detailed"
                }
                print(f"[CI] Using o3 with high reasoning effort")
            else:
                # Fallback for other models
                request_params["temperature"] = 0.7
                print(f"[CI] Using {settings.OPENAI_MODEL} with temperature control")

            # Start the analysis
            print(f"[CI] Starting competitive intelligence analysis with: {request_params}")
            
            # Send initial progress
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Initializing GPT-5 competitive intelligence analysis...', 'step': 'initialization'})}\n\n"
            
            # Execute the request with streaming
            response = client.responses.create(**request_params)
            
            # Track metrics
            thinking_steps = 0
            web_searches = 0
            content_chunks = []
            
            # Process streaming response
            for chunk in response:
                if hasattr(chunk, 'output') and chunk.output:
                    for item in chunk.output:
                        if hasattr(item, 'type'):
                            
                            # Handle reasoning/thinking steps
                            if item.type == 'reasoning':
                                thinking_steps += 1
                                thinking_content = ""
                                
                                if hasattr(item, 'summary') and item.summary:
                                    for summary_item in item.summary:
                                        if hasattr(summary_item, 'text'):
                                            thinking_content = summary_item.text
                                            break
                                
                                if thinking_content:
                                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content, 'step_number': thinking_steps})}\n\n"
                                    await asyncio.sleep(0.1)  # Small delay for UI smoothness
                            
                            # Handle web search calls
                            elif item.type == 'web_search_call':
                                web_searches += 1
                                search_query = ""
                                search_status = "unknown"
                                
                                if hasattr(item, 'action') and item.action:
                                    search_query = item.action.get('query', 'Searching...')
                                if hasattr(item, 'status'):
                                    search_status = item.status
                                
                                yield f"data: {json.dumps({'type': 'web_search', 'query': search_query, 'status': search_status, 'search_number': web_searches})}\n\n"
                                await asyncio.sleep(0.1)
                            
                            # Handle content/message output
                            elif item.type == 'message':
                                if hasattr(item, 'content') and item.content:
                                    for content_item in item.content:
                                        if hasattr(content_item, 'text'):
                                            content_chunks.append(content_item.text)
                                            
                                            # Send content chunk
                                            yield f"data: {json.dumps({'type': 'content', 'content': content_item.text, 'is_partial': True})}\n\n"
                                            
                                            # Extract citations if available
                                            citations = []
                                            if hasattr(content_item, 'annotations'):
                                                for ann in content_item.annotations:
                                                    citations.append({
                                                        "title": getattr(ann, 'title', 'Source'),
                                                        "url": getattr(ann, 'url', ''),
                                                        "start": getattr(ann, 'start_index', 0),
                                                        "end": getattr(ann, 'end_index', 0)
                                                    })
                                            
                                            if citations:
                                                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            
            # Combine all content chunks
            final_content = ''.join(content_chunks)
            
            if not final_content:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No content generated from analysis'})}\n\n"
                return
            
            # Prepare final metadata
            metadata = {
                "thinking_steps": thinking_steps,
                "web_searches": web_searches,
                "report_length": len(final_content),
                "model_used": settings.OPENAI_MODEL,
                "analysis_type": "gpt5_reasoning_with_search"
            }
            
            # Store the research results
            try:
                research_record = {
                    'id': str(uuid.uuid4()),
                    'user_id': user['uid'],
                    'research_query': request.research_query,
                    'competitors': request.competitors,
                    'focus_areas': request.focus_areas,
                    'time_horizon': request.time_horizon,
                    'depth': request.depth,
                    'report_content': final_content,
                    'metadata': metadata,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                result = supabase.table('competitive_intelligence_reports').insert(research_record).execute()
                report_id = result.data[0]['id'] if result.data else None
                
                # Send completion
                yield f"data: {json.dumps({'type': 'completion', 'report_id': report_id, 'content': final_content, 'metadata': metadata})}\n\n"
                
            except Exception as storage_error:
                print(f"Failed to store research: {storage_error}")
                # Still send completion even if storage fails
                yield f"data: {json.dumps({'type': 'completion', 'content': final_content, 'metadata': metadata})}\n\n"
                
        except Exception as e:
            error_message = f"Competitive intelligence analysis failed: {str(e)}"
            print(f"[CI] Error: {error_message}")
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

@router.get("/reports")
async def list_competitive_intelligence_reports(user=Depends(get_current_user)):
    """List all competitive intelligence reports for the user"""
    try:
        result = supabase.table('competitive_intelligence_reports')\
            .select("*")\
            .eq('user_id', user['uid'])\
            .order('created_at', desc=True)\
            .limit(50)\
            .execute()
        
        return {"reports": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")

@router.get("/reports/{report_id}")
async def get_competitive_intelligence_report(report_id: str, user=Depends(get_current_user)):
    """Get a specific competitive intelligence report"""
    try:
        result = supabase.table('competitive_intelligence_reports')\
            .select("*")\
            .eq('id', report_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return {"report": result.data}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Report not found")
        raise HTTPException(status_code=500, detail=f"Error fetching report: {str(e)}")

@router.delete("/reports/{report_id}")
async def delete_competitive_intelligence_report(report_id: str, user=Depends(get_current_user)):
    """Delete a competitive intelligence report"""
    try:
        result = supabase.table('competitive_intelligence_reports')\
            .delete()\
            .eq('id', report_id)\
            .eq('user_id', user['uid'])\
            .execute()
        
        return {"message": "Report deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting report: {str(e)}")
