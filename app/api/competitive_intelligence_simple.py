from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api/competitive-intelligence-simple", tags=["competitive-intelligence-simple"])

class CompetitiveIntelligenceRequest(BaseModel):
    query: str
    template: Optional[str] = "general"

@router.post("/analyze")
async def analyze_competitive_intelligence_simple(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    EXTREMELY SIMPLE competitive intelligence analysis.
    Just send to GPT-5 and return the raw response.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client unavailable")

        # Super simple system prompt
        system_prompt = f"""You are Oliver, a competitive intelligence analyst for financial institutions.
        Analyze the following query and provide strategic insights that work for any bank: {request.query}"""

        print(f"[CI-Simple] Starting analysis with query: {request.query[:100]}...")

        # Use the simplest possible GPT-5 call
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=request.query,
            instructions=system_prompt,
            reasoning={"effort": "minimal"},  # Fastest possible
            text={"verbosity": "medium"},
            max_output_tokens=3000
        )

        print(f"[CI-Simple] Got response, extracting content...")

        # Extract content - try every possible way
        content = ""
        
        # Method 1: output_text
        if hasattr(response, 'output_text') and response.output_text:
            content = response.output_text
            print(f"[CI-Simple] Got content via output_text: {len(content)} chars")
        
        # Method 2: output array
        elif hasattr(response, 'output') and response.output:
            print(f"[CI-Simple] Checking output array with {len(response.output)} items")
            for item in response.output:
                print(f"[CI-Simple] Item type: {getattr(item, 'type', 'unknown')}")
                if getattr(item, 'type', '') == 'message':
                    if hasattr(item, 'content') and item.content:
                        for content_item in item.content:
                            if getattr(content_item, 'type', '') == 'output_text':
                                content = getattr(content_item, 'text', '')
                                print(f"[CI-Simple] Got content via output array: {len(content)} chars")
                                break
                if content:
                    break
        
        # Method 3: Direct text access
        elif hasattr(response, 'text'):
            content = response.text
            print(f"[CI-Simple] Got content via direct text: {len(content)} chars")
        
        if not content:
            print(f"[CI-Simple] No content found. Response type: {type(response)}")
            print(f"[CI-Simple] Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
            raise HTTPException(status_code=500, detail="No content generated")

        print(f"[CI-Simple] SUCCESS: Generated {len(content)} characters")
        print(f"[CI-Simple] Content preview: {content[:200]}...")

        # Store in database
        try:
            analysis_record = {
                'id': str(uuid.uuid4()),
                'user_id': user['uid'],
                'query': request.query,
                'template': request.template,
                'analysis_content': content,
                'metadata': {
                    "model_used": settings.OPENAI_MODEL,
                    "reasoning_effort": "minimal",
                    "content_length": len(content)
                },
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('competitive_intelligence_analyses').insert(analysis_record).execute()
            analysis_id = result.data[0]['id'] if result.data else None
            print(f"[CI-Simple] Stored analysis: {analysis_id}")
            
        except Exception as storage_error:
            print(f"[CI-Simple] Storage failed: {storage_error}")
            # Continue anyway

        return {
            "success": True,
            "content": content,
            "query": request.query,
            "template": request.template
        }

    except Exception as e:
        print(f"[CI-Simple] ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/templates")
async def get_simple_templates():
    """Get simple analysis templates"""
    return {
        "templates": [
            {
                "id": "threats",
                "title": "Competitive Threats",
                "query": "Analyze current competitive threats in digital banking and fintech competition for regional banks"
            },
            {
                "id": "performance",
                "title": "Performance Analysis",
                "query": "Compare regional bank financial performance and market position against competitors"
            },
            {
                "id": "strategy",
                "title": "Strategic Opportunities",
                "query": "Identify strategic opportunities and market positioning advantages for regional banks"
            }
        ]
    }
