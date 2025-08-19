from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
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

@router.post("/analyze")
async def analyze_competitive_intelligence(
    request: CompetitiveIntelligenceRequest,
    user=Depends(get_current_user)
):
    """
    Simple competitive intelligence analysis using GPT-5.
    Returns raw GPT-5 output for maximum quality and simplicity.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="Analysis service unavailable")

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

        # Configure GPT-5 with high reasoning for quality analysis
        request_params = {
            "model": settings.OPENAI_MODEL,
            "input": request.query,
            "instructions": system_prompt,
            "max_output_tokens": 5000,
            "store": True
        }
        
        # Add GPT-5 specific parameters for highest quality
        if settings.OPENAI_MODEL.startswith("gpt-5"):
            request_params["reasoning"] = {"effort": "high"}  # Maximum reasoning quality
            request_params["text"] = {"verbosity": "high"}    # Comprehensive output
            print(f"[CI] Using GPT-5 with high reasoning effort")
        elif settings.OPENAI_MODEL.startswith("o3"):
            request_params["reasoning"] = {"effort": "high", "summary": "detailed"}
        else:
            request_params["temperature"] = 0.7

        # Execute the analysis
        print(f"[CI] Starting competitive intelligence analysis")
        response = client.responses.create(**request_params)
        
        # Extract content using proven pattern
        content = ""
        if response.output:
            for item in response.output:
                if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                    for c in item.content:
                        if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                            content = c.text
                            break
                if content:
                    break
        
        # Fallback to output_text
        if not content and hasattr(response, 'output_text'):
            content = response.output_text
        
        if not content:
            raise HTTPException(status_code=500, detail="No content generated from analysis")

        print(f"[CI] Generated {len(content)} characters of analysis")

        # Store the analysis
        try:
            analysis_record = {
                'id': str(uuid.uuid4()),
                'user_id': user['uid'],
                'query': request.query,
                'template': request.template,
                'analysis_content': content,
                'metadata': {
                    "model_used": settings.OPENAI_MODEL,
                    "template": request.template,
                    "content_length": len(content)
                },
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('competitive_intelligence_analyses').insert(analysis_record).execute()
            analysis_id = result.data[0]['id'] if result.data else None
            
            return {
                "analysis_id": analysis_id,
                "content": content,
                "metadata": analysis_record['metadata']
            }
            
        except Exception as storage_error:
            print(f"Failed to store analysis: {storage_error}")
            # Still return the content even if storage fails
            return {
                "content": content,
                "metadata": {
                    "model_used": settings.OPENAI_MODEL,
                    "template": request.template,
                    "content_length": len(content)
                }
            }

    except Exception as e:
        print(f"Competitive intelligence error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

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
