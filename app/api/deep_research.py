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
            
            # Configure Deep Research API call with background mode
            research_params = {
                "model": "o3-deep-research" if request.depth == "comprehensive" else "o4-mini-deep-research",
                "input": refined_query,
                "instructions": system_prompt,
                "background": True,  # Essential for long-running research
                "reasoning": {
                    "summary": "detailed" if request.depth == "comprehensive" else "auto"
                },
                "tools": [
                    {
                        "type": "web_search_preview"
                    }
                ],
                "store": True,  # Store for debugging and analysis
                "max_tool_calls": 50 if request.depth == "comprehensive" else 25  # Control cost/latency
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
                # Since Deep Research doesn't support real-time streaming, we'll:
                # 1. Start the background research
                # 2. Show simulated progress with realistic timing
                # 3. Poll for completion
                
                step3.content = "Starting Deep Research in background mode..."
                yield await send_sse_message(step3)
                
                # Execute Deep Research API call in background mode
                print(f"🔍 Starting Deep Research with params: {research_params}")
                response = client.responses.create(**research_params)
                
                # Get the response ID for polling
                response_id = getattr(response, 'id', None)
                print(f"📋 Deep Research started with ID: {response_id}")
                
                if not response_id:
                    raise Exception("No response ID received from Deep Research API")
                
                step3.status = "completed"
                step3.content = f"Deep Research initiated with ID: {response_id}"
                yield await send_sse_message(step3)
                
                # Step 4: Polling for completion with simulated progress
                step4 = create_research_step(
                    step_type="polling",
                    title="Monitoring Research Progress",
                    content="Polling Deep Research API for completion...",
                    status="active"
                )
                yield await send_sse_message(step4)
                
                # Simulate realistic research progress while polling
                progress_messages = [
                    "Oliver is planning research strategy...",
                    "Executing initial web searches...",
                    "Analyzing competitor financial data...",
                    "Gathering market intelligence...",
                    "Synthesizing competitive insights...",
                    "Generating structured report...",
                    "Finalizing analysis and citations..."
                ]
                
                search_count = 0
                reasoning_count = 0
                max_polls = 60  # 5 minutes max (5s intervals)
                poll_count = 0
                
                while poll_count < max_polls:
                    try:
                        # Check if research is complete
                        status_response = client.responses.retrieve(response_id)
                        
                        if hasattr(status_response, 'status'):
                            if status_response.status == 'completed':
                                # Research is complete!
                                step4.status = "completed"
                                step4.content = "Deep Research completed successfully!"
                                yield await send_sse_message(step4)
                                
                                # Extract the final report and intermediate steps
                                final_content = ""
                                citations = []
                                web_searches = []
                                reasoning_steps = []
                                
                                if hasattr(status_response, 'output') and status_response.output:
                                    for item in status_response.output:
                                        if hasattr(item, 'type'):
                                            if item.type == 'web_search_call':
                                                web_searches.append(item)
                                            elif item.type == 'reasoning':
                                                reasoning_steps.append(item)
                                            elif item.type == 'message':
                                                if hasattr(item, 'content') and item.content:
                                                    for content_item in item.content:
                                                        if hasattr(content_item, 'text'):
                                                            final_content = content_item.text
                                                            
                                                            # Extract citations
                                                            if hasattr(content_item, 'annotations'):
                                                                for ann in content_item.annotations:
                                                                    citations.append({
                                                                        "title": getattr(ann, 'title', 'Source'),
                                                                        "url": getattr(ann, 'url', ''),
                                                                        "start": getattr(ann, 'start_index', 0),
                                                                        "end": getattr(ann, 'end_index', 0)
                                                                    })
                                
                                if not final_content:
                                    raise Exception("No content received from completed Deep Research")
                                
                                # Send completion with actual research data
                                final_step = create_research_step(
                                    step_type="completion",
                                    title="Competitive Intelligence Report Ready",
                                    content=final_content,
                                    status="completed",
                                    metadata={
                                        "search_count": len(web_searches),
                                        "reasoning_steps": len(reasoning_steps),
                                        "citations": len(citations),
                                        "report_length": len(final_content),
                                        "citations_detail": citations,
                                        "response_id": response_id
                                    }
                                )
                                yield await send_sse_message(final_step)
                                
                                # Store in database
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
                                        'response_id': response_id,
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
                                    print(f"Failed to store research report: {storage_error}")
                                
                                break  # Exit polling loop
                                
                            elif status_response.status == 'failed':
                                error_msg = getattr(status_response, 'error', {}).get('message', 'Deep Research failed')
                                raise Exception(f"Deep Research failed: {error_msg}")
                            
                            elif status_response.status == 'in_progress':
                                # Show progress update
                                progress_index = min(poll_count // 5, len(progress_messages) - 1)
                                step4.content = progress_messages[progress_index]
                                yield await send_sse_message(step4)
                        
                        # Wait before next poll
                        await asyncio.sleep(5)  # Poll every 5 seconds
                        poll_count += 1
                        
                    except Exception as poll_error:
                        print(f"Polling error: {poll_error}")
                        await asyncio.sleep(5)
                        poll_count += 1
                
                # If we exit the loop without completion, it's a timeout
                if poll_count >= max_polls:
                    raise Exception("Deep Research timed out after 5 minutes. This may be normal for comprehensive research - try using background mode with webhooks for production.")
                
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

@router.post("/webhook/completion")
async def handle_deep_research_webhook(payload: Dict[str, Any]):
    """
    Webhook endpoint for Deep Research completion notifications.
    This would be used in production with background mode.
    """
    try:
        # Extract webhook data
        response_id = payload.get('response_id')
        status = payload.get('status')
        
        if status == 'completed' and response_id:
            # Retrieve the completed research
            client = openai_manager.get_client()
            if client:
                completed_response = client.responses.retrieve(response_id)
                
                # Process and store the results
                # This would update the database and notify the frontend
                # via WebSocket or similar real-time mechanism
                
                print(f"✅ Deep Research webhook: {response_id} completed")
                return {"message": "Webhook processed successfully"}
        
        return {"message": "Webhook received"}
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")
