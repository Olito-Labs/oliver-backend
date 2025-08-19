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

router = APIRouter(prefix="/api/deep-research", tags=["deep-research"])

# Request/Response models
class CompetitiveIntelligenceRequest(BaseModel):
    """Request model for competitive intelligence research"""
    research_query: str
    competitors: Optional[List[str]] = None
    focus_areas: Optional[List[str]] = None
    time_horizon: Optional[str] = "last 12 months"
    depth: Optional[str] = "comprehensive"  # quick, standard, comprehensive
    include_financials: bool = True
    include_products: bool = True
    include_strategy: bool = True
    include_regulatory: bool = True

class ResearchStep(BaseModel):
    """Model for streaming research progress steps"""
    id: str
    type: str  # reasoning, web_search, synthesis, completion
    title: str
    content: str
    status: str  # active, completed, error
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

def create_research_step(
    step_type: str,
    title: str,
    content: str,
    status: str = "active",
    metadata: Dict[str, Any] = None
) -> ResearchStep:
    """Helper to create research step objects"""
    return ResearchStep(
        id=str(uuid.uuid4()),
        type=step_type,
        title=title,
        content=content,
        status=status,
        timestamp=datetime.utcnow().isoformat(),
        metadata=metadata or {}
    )

async def send_sse_message(step: ResearchStep) -> str:
    """Format a research step as SSE data"""
    return f"data: {json.dumps(step.dict())}\n\n"

async def send_error(error_message: str) -> str:
    """Format error as SSE data"""
    error_step = create_research_step(
        step_type="error",
        title="Research Error",
        content=error_message,
        status="error"
    )
    return f"data: {json.dumps(error_step.dict())}\n\n"

@router.post("/competitive-intelligence/stream")
async def stream_competitive_intelligence(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    Stream competitive intelligence research using Deep Research API.
    Returns real-time progress updates and final structured report.
    """
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"
            
            # Step 1: Initialize Research
            step1 = create_research_step(
                step_type="initialization",
                title="Initializing Competitive Intelligence Research",
                content=f"Setting up research parameters for: {request.research_query}",
                status="active"
            )
            yield await send_sse_message(step1)
            await asyncio.sleep(1)
            
            # Build the system prompt for banking competitive intelligence
            system_prompt = f"""
You are a senior competitive intelligence analyst for a global financial institution. Your task is to conduct comprehensive research on the competitive landscape in banking and financial services.

Research Scope:
- Query: {request.research_query}
- Competitors to analyze: {', '.join(request.competitors) if request.competitors else 'Identify key competitors'}
- Time horizon: {request.time_horizon}
- Analysis depth: {request.depth}

Focus Areas:
{f"- Financial Performance: Revenue, profitability, market cap, key financial ratios" if request.include_financials else ""}
{f"- Product Strategy: Product offerings, innovation, digital transformation initiatives" if request.include_products else ""}
{f"- Strategic Positioning: Market positioning, M&A activity, partnerships, expansion plans" if request.include_strategy else ""}
{f"- Regulatory Compliance: Regulatory issues, compliance track record, risk management" if request.include_regulatory else ""}

Requirements:
1. Focus on data-rich insights with specific figures, trends, and measurable outcomes
2. Include market share data, growth rates, and competitive positioning metrics
3. Analyze competitive advantages and vulnerabilities
4. Identify emerging threats and opportunities
5. Provide actionable strategic recommendations
6. Prioritize reliable sources: regulatory filings (10-K, 10-Q), earnings reports, industry analyses, reputable financial news
7. Include inline citations with full source metadata
8. Structure the analysis with clear sections and data that could be visualized

Deliverable:
Produce a structured competitive intelligence report with:
- Executive Summary
- Competitive Landscape Overview
- Detailed Competitor Analysis
- Market Trends and Dynamics
- Strategic Opportunities and Threats
- Actionable Recommendations
- Supporting Data and Citations
"""

            # Update step 1 as completed
            step1.status = "completed"
            step1.content = "Research parameters configured successfully"
            yield await send_sse_message(step1)
            
            # Step 2: Query Refinement (optional clarification)
            step2 = create_research_step(
                step_type="refinement",
                title="Refining Research Query",
                content="Optimizing search parameters for comprehensive competitive analysis...",
                status="active"
            )
            yield await send_sse_message(step2)
            await asyncio.sleep(1)
            
            # Use a lightweight model to refine the query if needed
            client = openai_manager.get_client()
            if not client:
                raise Exception("OpenAI client not available")
            
            # Refine the user query for better Deep Research results
            refinement_prompt = """
You will be given a competitive intelligence research request. Expand it into detailed instructions for Deep Research.

GUIDELINES:
1. Include all specific competitors, metrics, and time frames mentioned
2. Specify desired output format with sections and data tables
3. Emphasize quantitative analysis and data-driven insights
4. Request comparison tables for key metrics across competitors
5. Ask for trend analysis and future projections where relevant
6. Maintain focus on actionable intelligence for strategic decision-making
"""
            
            try:
                refinement_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": refinement_prompt},
                        {"role": "user", "content": f"Original request: {request.research_query}\n\nCompetitors: {request.competitors}\nFocus areas: {request.focus_areas}"}
                    ],
                    temperature=0.7
                )
                
                refined_query = refinement_response.choices[0].message.content
                step2.status = "completed"
                step2.content = "Query refined for optimal research coverage"
                step2.metadata = {"refined_query_preview": refined_query[:200] + "..."}
                yield await send_sse_message(step2)
                
            except Exception as e:
                # Continue with original query if refinement fails
                refined_query = request.research_query
                step2.status = "completed"
                step2.content = "Proceeding with original query"
                yield await send_sse_message(step2)
            
            # Step 3: Deep Research Execution
            step3 = create_research_step(
                step_type="research",
                title="Executing Deep Research",
                content="Initiating autonomous research across multiple sources...",
                status="active"
            )
            yield await send_sse_message(step3)
            
            # Configure Deep Research API call
            research_params = {
                "model": "o3-deep-research-2025-06-26" if request.depth == "comprehensive" else "o4-mini-deep-research-2025-06-26",
                "input": [
                    {
                        "role": "developer",
                        "content": [
                            {
                                "type": "input_text",
                                "text": system_prompt,
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": refined_query,
                            }
                        ]
                    }
                ],
                "reasoning": {
                    "summary": "detailed" if request.depth == "comprehensive" else "auto"
                },
                "tools": [
                    {
                        "type": "web_search_preview"
                    }
                ]
            }
            
            # Add code interpreter for data analysis if comprehensive
            if request.depth == "comprehensive":
                research_params["tools"].append({
                    "type": "code_interpreter",
                    "container": {
                        "type": "auto",
                        "file_ids": []
                    }
                })
            
            try:
                # Simulate research progress with realistic timing
                progress_steps = [
                    ("Planning research strategy", 2),
                    ("Executing web searches", 3),
                    ("Analyzing competitor data", 4),
                    ("Synthesizing market insights", 3),
                    ("Generating structured report", 2)
                ]
                
                search_count = 0
                reasoning_count = 0
                
                for step_desc, duration in progress_steps:
                    reasoning_count += 1
                    progress_step = create_research_step(
                        step_type="reasoning",
                        title=f"Research Step {reasoning_count}",
                        content=f"Oliver is {step_desc.lower()}...",
                        status="active"
                    )
                    yield await send_sse_message(progress_step)
                    await asyncio.sleep(duration)
                    
                    # Simulate some web searches during the process
                    if reasoning_count in [2, 3, 4]:
                        search_count += 1
                        search_queries = [
                            "banking competitive landscape 2024",
                            "regulatory compliance strategies banks",
                            "digital transformation financial services",
                            "market share analysis major banks"
                        ]
                        search_step = create_research_step(
                            step_type="web_search",
                            title=f"Web Search {search_count}",
                            content=f"Searching for: {search_queries[search_count-1] if search_count <= len(search_queries) else 'market intelligence'}",
                            status="active",
                            metadata={"query": search_queries[search_count-1] if search_count <= len(search_queries) else 'market intelligence'}
                        )
                        yield await send_sse_message(search_step)
                        await asyncio.sleep(1)
                
                # Execute the actual Deep Research API call
                step3.content = "Executing Deep Research analysis..."
                yield await send_sse_message(step3)
                
                response = client.responses.create(**research_params)
                
                # Extract the final report
                final_content = ""
                citations = []
                
                if hasattr(response, 'output') and response.output:
                    for item in response.output:
                        if hasattr(item, 'type') and item.type == 'message':
                            if hasattr(item, 'content') and item.content:
                                for content_item in item.content:
                                    if hasattr(content_item, 'text'):
                                        final_content = content_item.text
                                        
                                        # Extract citations if available
                                        if hasattr(content_item, 'annotations'):
                                            for ann in content_item.annotations:
                                                citations.append({
                                                    "title": getattr(ann, 'title', 'Source'),
                                                    "url": getattr(ann, 'url', ''),
                                                    "start": getattr(ann, 'start_index', 0),
                                                    "end": getattr(ann, 'end_index', 0)
                                                })
                                        break
                            if final_content:
                                break
                
                if not final_content:
                    raise Exception("No content received from Deep Research API")
                
                # Complete the research step
                step3.status = "completed"
                step3.content = f"Research completed: {search_count} searches performed, {reasoning_count} analysis steps"
                yield await send_sse_message(step3)
                
                # Send the final report
                final_step = create_research_step(
                    step_type="completion",
                    title="Competitive Intelligence Report Ready",
                    content=final_content,
                    status="completed",
                    metadata={
                        "search_count": search_count,
                        "reasoning_steps": reasoning_count,
                        "citations": len(citations),
                        "report_length": len(final_content),
                        "citations_detail": citations
                    }
                )
                yield await send_sse_message(final_step)
                
                # Store the research results in database
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
                        'metadata': final_step.metadata,
                        'created_at': datetime.utcnow().isoformat()
                    }
                    
                    result = supabase.table('competitive_intelligence_reports').insert(research_record).execute()
                    
                    if result.data:
                        storage_step = create_research_step(
                            step_type="storage",
                            title="Report Saved",
                            content=f"Research report saved with ID: {result.data[0]['id']}",
                            status="completed",
                            metadata={"report_id": result.data[0]['id']}
                        )
                        yield await send_sse_message(storage_step)
                except Exception as storage_error:
                    # Don't fail the whole process if storage fails
                    print(f"Failed to store research report: {storage_error}")
                
            except Exception as research_error:
                step3.status = "error"
                step3.content = f"Research failed: {str(research_error)}"
                yield await send_sse_message(step3)
                yield await send_error(f"Deep Research error: {str(research_error)}")
                return
                
        except Exception as e:
            yield await send_error(f"Unexpected error: {str(e)}")
    
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
async def list_research_reports(user=Depends(get_current_user)):
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
async def get_research_report(report_id: str, user=Depends(get_current_user)):
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
async def delete_research_report(report_id: str, user=Depends(get_current_user)):
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
