from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
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

router = APIRouter(prefix="/api/deep-research-v2", tags=["deep-research-v2"])

# Request/Response models
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

class ResearchJobResponse(BaseModel):
    """Response when starting a research job"""
    job_id: str
    status: str
    message: str
    estimated_completion: str

class ResearchStatusResponse(BaseModel):
    """Response for job status checks"""
    job_id: str
    status: str  # pending, in_progress, completed, failed
    progress: int  # 0-100
    current_step: Optional[str] = None
    report_content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

async def execute_deep_research_job(job_id: str, request_data: Dict[str, Any], user_id: str):
    """
    Background job to execute Deep Research.
    This runs independently of the HTTP request.
    """
    try:
        print(f"🚀 Starting Deep Research job {job_id}")
        
        # Update job status to in_progress
        supabase.table('competitive_intelligence_jobs').update({
            'status': 'in_progress',
            'progress': 10,
            'current_step': 'Initializing Deep Research',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', job_id).execute()
        
        # Build the system prompt
        system_prompt = f"""
You are a senior competitive intelligence analyst for a global financial institution. Conduct comprehensive research on the competitive landscape in banking and financial services.

Research Scope:
- Query: {request_data['research_query']}
- Competitors: {', '.join(request_data.get('competitors', [])) if request_data.get('competitors') else 'Identify key competitors'}
- Time horizon: {request_data['time_horizon']}
- Analysis depth: {request_data['depth']}

Focus Areas:
{f"- Financial Performance: Revenue, profitability, market cap, key financial ratios" if request_data.get('include_financials') else ""}
{f"- Product Strategy: Product offerings, innovation, digital transformation initiatives" if request_data.get('include_products') else ""}
{f"- Strategic Positioning: Market positioning, M&A activity, partnerships, expansion plans" if request_data.get('include_strategy') else ""}
{f"- Regulatory Compliance: Regulatory issues, compliance track record, risk management" if request_data.get('include_regulatory') else ""}

Requirements:
1. Focus on data-rich insights with specific figures, trends, and measurable outcomes
2. Include market share data, growth rates, and competitive positioning metrics
3. Analyze competitive advantages and vulnerabilities
4. Identify emerging threats and opportunities
5. Provide actionable strategic recommendations
6. Prioritize reliable sources: regulatory filings (10-K, 10-Q), earnings reports, industry analyses
7. Include inline citations with full source metadata
8. Structure with clear sections that could be visualized

Format as a comprehensive report with:
- Executive Summary
- Competitive Landscape Overview  
- Detailed Competitor Analysis
- Market Trends and Dynamics
- Strategic Opportunities and Threats
- Actionable Recommendations
"""

        # Update progress
        supabase.table('competitive_intelligence_jobs').update({
            'progress': 20,
            'current_step': 'Starting Deep Research Analysis'
        }).eq('id', job_id).execute()

        # Get OpenAI client
        client = openai_manager.get_client()
        if not client:
            raise Exception("OpenAI client not available")

        # Execute Deep Research
        research_params = {
            "model": "o3-deep-research" if request_data['depth'] == "comprehensive" else "o4-mini-deep-research",
            "input": request_data['research_query'],
            "instructions": system_prompt,
            "tools": [{"type": "web_search_preview"}],
            "store": True,
            "max_tool_calls": 30 if request_data['depth'] == "comprehensive" else 15
        }
        
        # Add code interpreter for comprehensive analysis
        if request_data['depth'] == "comprehensive":
            research_params["tools"].append({
                "type": "code_interpreter",
                "container": {"type": "auto", "file_ids": []}
            })

        print(f"🔍 Executing Deep Research with params: {research_params}")
        
        # For long-running tasks, we'll use synchronous mode but with proper error handling
        # Background mode requires webhook setup which is complex for this demo
        response = client.responses.create(**research_params)
        
        print(f"📋 Deep Research response received")
        
        # Update progress
        supabase.table('competitive_intelligence_jobs').update({
            'progress': 80,
            'current_step': 'Processing Research Results'
        }).eq('id', job_id).execute()

        # Extract results
        final_content = ""
        citations = []
        web_searches = []
        reasoning_steps = []
        
        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'type'):
                    if item.type == 'web_search_call':
                        web_searches.append({
                            "query": getattr(item, 'action', {}).get('query', 'Unknown'),
                            "status": getattr(item, 'status', 'unknown')
                        })
                    elif item.type == 'reasoning':
                        if hasattr(item, 'summary') and item.summary:
                            for summary_item in item.summary:
                                if hasattr(summary_item, 'text'):
                                    reasoning_steps.append(summary_item.text)
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
            raise Exception("No content received from Deep Research API")

        # Prepare metadata
        metadata = {
            "search_count": len(web_searches),
            "reasoning_steps": len(reasoning_steps),
            "citations": len(citations),
            "report_length": len(final_content),
            "citations_detail": citations,
            "web_searches": web_searches,
            "reasoning_detail": reasoning_steps[:5]  # First 5 reasoning steps
        }

        # Store the completed research
        research_record = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'research_query': request_data['research_query'],
            'competitors': request_data.get('competitors'),
            'focus_areas': request_data.get('focus_areas'),
            'time_horizon': request_data['time_horizon'],
            'depth': request_data['depth'],
            'report_content': final_content,
            'metadata': metadata,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('competitive_intelligence_reports').insert(research_record).execute()
        report_id = result.data[0]['id'] if result.data else None

        # Update job as completed
        supabase.table('competitive_intelligence_jobs').update({
            'status': 'completed',
            'progress': 100,
            'current_step': 'Research Complete',
            'report_content': final_content,
            'metadata': metadata,
            'report_id': report_id,
            'completed_at': datetime.utcnow().isoformat()
        }).eq('id', job_id).execute()

        print(f"✅ Deep Research job {job_id} completed successfully")

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Deep Research job {job_id} failed: {error_msg}")
        
        # Update job as failed
        supabase.table('competitive_intelligence_jobs').update({
            'status': 'failed',
            'current_step': 'Research Failed',
            'error_message': error_msg,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', job_id).execute()

@router.post("/competitive-intelligence/start", response_model=ResearchJobResponse)
async def start_competitive_intelligence_research(
    request: CompetitiveIntelligenceRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    Start a competitive intelligence research job.
    Returns immediately with job ID for status polling.
    """
    try:
        # Create job record
        job_id = str(uuid.uuid4())
        
        job_record = {
            'id': job_id,
            'user_id': user['uid'],
            'status': 'pending',
            'progress': 0,
            'current_step': 'Job Created',
            'request_data': request.dict(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('competitive_intelligence_jobs').insert(job_record).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create research job")

        # Start background task
        background_tasks.add_task(
            execute_deep_research_job,
            job_id,
            request.dict(),
            user['uid']
        )

        return ResearchJobResponse(
            job_id=job_id,
            status="pending",
            message="Research job started. Use the job ID to check progress.",
            estimated_completion="10-20 minutes"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start research: {str(e)}")

@router.get("/jobs/{job_id}/status", response_model=ResearchStatusResponse)
async def get_research_status(job_id: str, user=Depends(get_current_user)):
    """Get the status of a research job"""
    try:
        result = supabase.table('competitive_intelligence_jobs')\
            .select("*")\
            .eq('id', job_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = result.data
        
        return ResearchStatusResponse(
            job_id=job_id,
            status=job['status'],
            progress=job.get('progress', 0),
            current_step=job.get('current_step'),
            report_content=job.get('report_content'),
            metadata=job.get('metadata'),
            error_message=job.get('error_message')
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=500, detail=f"Error fetching job status: {str(e)}")

@router.get("/jobs", response_model=Dict[str, List[Dict[str, Any]]])
async def list_research_jobs(user=Depends(get_current_user)):
    """List all research jobs for the user"""
    try:
        result = supabase.table('competitive_intelligence_jobs')\
            .select("*")\
            .eq('user_id', user['uid'])\
            .order('created_at', desc=True)\
            .limit(20)\
            .execute()
        
        return {"jobs": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching jobs: {str(e)}")

# Keep the streaming endpoint for immediate feedback during job polling
@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, user=Depends(get_current_user)):
    """Stream job progress updates"""
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            last_progress = -1
            max_polls = 240  # 20 minutes max (5s intervals)
            poll_count = 0
            
            while poll_count < max_polls:
                try:
                    # Get current job status
                    result = supabase.table('competitive_intelligence_jobs')\
                        .select("*")\
                        .eq('id', job_id)\
                        .eq('user_id', user['uid'])\
                        .single()\
                        .execute()
                    
                    if not result.data:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                        return
                    
                    job = result.data
                    current_progress = job.get('progress', 0)
                    
                    # Send update if progress changed
                    if current_progress != last_progress:
                        progress_data = {
                            "type": "progress",
                            "job_id": job_id,
                            "status": job['status'],
                            "progress": current_progress,
                            "current_step": job.get('current_step', 'Processing...'),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        yield f"data: {json.dumps(progress_data)}\n\n"
                        last_progress = current_progress
                    
                    # Check if completed
                    if job['status'] == 'completed':
                        completion_data = {
                            "type": "completion",
                            "job_id": job_id,
                            "report_content": job.get('report_content', ''),
                            "metadata": job.get('metadata', {}),
                            "report_id": job.get('report_id')
                        }
                        yield f"data: {json.dumps(completion_data)}\n\n"
                        break
                    
                    elif job['status'] == 'failed':
                        error_data = {
                            "type": "error",
                            "job_id": job_id,
                            "message": job.get('error_message', 'Research failed')
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        break
                    
                    await asyncio.sleep(5)  # Poll every 5 seconds
                    poll_count += 1
                    
                except Exception as poll_error:
                    print(f"Polling error: {poll_error}")
                    await asyncio.sleep(5)
                    poll_count += 1
            
            # Timeout
            if poll_count >= max_polls:
                yield f"data: {json.dumps({'type': 'timeout', 'message': 'Research is taking longer than expected. Check back later.'})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Stream error: {str(e)}'})}\n\n"
    
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
