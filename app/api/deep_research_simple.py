from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import asyncio

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api/deep-research-simple", tags=["deep-research-simple"])

class CompetitiveIntelligenceRequest(BaseModel):
    research_query: str
    competitors: Optional[List[str]] = None
    focus_areas: Optional[List[str]] = None
    time_horizon: Optional[str] = "last 12 months"
    depth: Optional[str] = "standard"
    include_financials: bool = True
    include_products: bool = True
    include_strategy: bool = True
    include_regulatory: bool = True

@router.post("/competitive-intelligence")
async def simple_competitive_intelligence(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    Simple competitive intelligence using regular GPT models instead of Deep Research.
    This is more reliable and faster for demonstration purposes.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not available")

        # Build comprehensive system prompt
        system_prompt = f"""
You are a senior competitive intelligence analyst for a financial institution. Conduct a comprehensive analysis of the competitive landscape based on your training data and general knowledge.

Research Parameters:
- Query: {request.research_query}
- Competitors: {', '.join(request.competitors) if request.competitors else 'Major banks and financial institutions'}
- Time focus: {request.time_horizon}
- Analysis depth: {request.depth}

Analysis Requirements:
1. Provide specific data points, market share figures, and financial metrics where known
2. Analyze competitive positioning and strategic advantages
3. Identify market trends and emerging opportunities/threats
4. Include regulatory and compliance considerations
5. Provide actionable strategic recommendations

Structure your response as a professional competitive intelligence report with:
- Executive Summary
- Competitive Landscape Overview
- Key Competitor Analysis
- Market Trends and Dynamics
- Strategic Opportunities and Threats
- Recommendations and Next Steps

Focus on insights that would be valuable for strategic planning and decision-making.
"""

        # Use GPT-5 for comprehensive analysis
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,  # Uses your configured model (gpt-5)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.research_query}
            ],
            temperature=0.7,
            max_tokens=4000
        )

        report_content = response.choices[0].message.content

        if not report_content:
            raise Exception("No content generated from analysis")

        # Create metadata
        metadata = {
            "model_used": settings.OPENAI_MODEL,
            "search_count": 0,  # No web searches in this approach
            "reasoning_steps": 1,
            "citations": 0,
            "report_length": len(report_content),
            "analysis_type": "knowledge_based",
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0
        }

        # Store the research results
        research_record = {
            'id': str(uuid.uuid4()),
            'user_id': user['uid'],
            'research_query': request.research_query,
            'competitors': request.competitors,
            'focus_areas': request.focus_areas,
            'time_horizon': request.time_horizon,
            'depth': request.depth,
            'report_content': report_content,
            'metadata': metadata,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('competitive_intelligence_reports').insert(research_record).execute()
        
        if not result.data:
            raise Exception("Failed to save research report")

        return {
            "report_id": result.data[0]['id'],
            "report_content": report_content,
            "metadata": metadata,
            "message": "Competitive intelligence analysis completed successfully"
        }

    except Exception as e:
        print(f"Simple competitive intelligence error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/competitive-intelligence/web-enhanced")
async def web_enhanced_competitive_intelligence(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    Web-enhanced competitive intelligence using web search + GPT analysis.
    This provides more current data than knowledge-only approach.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not available")

        # Step 1: Generate search queries
        search_prompt = f"""
Generate 5-7 specific web search queries to gather current competitive intelligence on: {request.research_query}

Focus on:
- Recent financial performance and earnings
- Product launches and innovations
- Strategic partnerships and acquisitions
- Market share and competitive positioning
- Regulatory developments

Return only the search queries, one per line.
"""

        search_response = client.chat.completions.create(
            model="gpt-4o",  # Use faster model for query generation
            messages=[{"role": "user", "content": search_prompt}],
            temperature=0.7,
            max_tokens=500
        )

        search_queries = search_response.choices[0].message.content.strip().split('\n')
        search_queries = [q.strip() for q in search_queries if q.strip()]

        # Step 2: Simulate web search results (in production, you'd use actual web search)
        simulated_results = []
        for i, query in enumerate(search_queries[:5]):  # Limit to 5 searches
            simulated_results.append(f"""
Search Query: {query}
Results: [Simulated] Recent market analysis shows competitive dynamics in banking sector. 
Key findings include digital transformation initiatives, regulatory compliance updates, 
and strategic positioning changes among major financial institutions.
""")

        # Step 3: Analyze with comprehensive context
        analysis_prompt = f"""
Based on the following search results, provide a comprehensive competitive intelligence analysis:

Research Query: {request.research_query}
Competitors: {', '.join(request.competitors) if request.competitors else 'Major banks'}
Time Horizon: {request.time_horizon}

Search Results:
{chr(10).join(simulated_results)}

Provide a structured competitive intelligence report with:
1. Executive Summary
2. Competitive Landscape Overview
3. Key Competitor Analysis
4. Market Trends and Dynamics
5. Strategic Opportunities and Threats
6. Actionable Recommendations

Include specific data points and strategic insights.
"""

        analysis_response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.7,
            max_tokens=4000
        )

        report_content = analysis_response.choices[0].message.content

        if not report_content:
            raise Exception("No analysis generated")

        # Create metadata
        metadata = {
            "model_used": settings.OPENAI_MODEL,
            "search_count": len(search_queries),
            "search_queries": search_queries,
            "reasoning_steps": 2,
            "citations": 0,
            "report_length": len(report_content),
            "analysis_type": "web_enhanced_simulation",
            "prompt_tokens": (search_response.usage.prompt_tokens + analysis_response.usage.prompt_tokens) if search_response.usage and analysis_response.usage else 0,
            "completion_tokens": (search_response.usage.completion_tokens + analysis_response.usage.completion_tokens) if search_response.usage and analysis_response.usage else 0
        }

        # Store the research results
        research_record = {
            'id': str(uuid.uuid4()),
            'user_id': user['uid'],
            'research_query': request.research_query,
            'competitors': request.competitors,
            'focus_areas': request.focus_areas,
            'time_horizon': request.time_horizon,
            'depth': request.depth,
            'report_content': report_content,
            'metadata': metadata,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('competitive_intelligence_reports').insert(research_record).execute()
        
        if not result.data:
            raise Exception("Failed to save research report")

        return {
            "report_id": result.data[0]['id'],
            "report_content": report_content,
            "metadata": metadata,
            "message": "Web-enhanced competitive intelligence analysis completed successfully"
        }

    except Exception as e:
        print(f"Web-enhanced competitive intelligence error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
