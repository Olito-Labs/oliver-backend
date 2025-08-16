# app/api/presentations.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import json
from datetime import datetime

from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.supabase_client import get_supabase_client
from app.config import settings

router = APIRouter(prefix="/api/presentations", tags=["presentations"])

# ============================================================================
# Pydantic Models
# ============================================================================

class PresentationSlide(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(..., regex="^(title|content|two-column|conclusion)$")
    title: str
    content: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class GeneratePresentationRequest(BaseModel):
    study_id: str
    prompt: str
    slide_count: int = Field(default=5, ge=3, le=20)
    audience: str = Field(default="management", regex="^(board|regulators|management|staff)$")
    tone: str = Field(default="formal", regex="^(formal|conversational|technical)$")
    include_context: bool = True
    user_id: str

class ExportPresentationRequest(BaseModel):
    presentation_id: str
    format: str = Field(..., regex="^(html|pdf)$")
    presentation_data: Dict[str, Any]

class PresentationResponse(BaseModel):
    presentation_id: str
    title: str
    description: str
    slides: List[PresentationSlide]
    metadata: Dict[str, Any]

# ============================================================================
# Helper Functions
# ============================================================================

async def get_study_context(study_id: str, user_id: str) -> Dict[str, Any]:
    """Get context from examination prep study for presentation generation"""
    try:
        supabase = get_supabase_client()
        
        # Get study details
        study_response = supabase.table('exam_studies').select('*').eq('id', study_id).eq('user_id', user_id).execute()
        if not study_response.data:
            return {}
        
        study = study_response.data[0]
        context = {
            'study_title': study.get('title', ''),
            'study_description': study.get('description', ''),
            'workflow_type': study.get('workflow_type', ''),
        }
        
        # Get examination requests if available
        requests_response = supabase.table('exam_requests').select('*').eq('study_id', study_id).eq('user_id', user_id).limit(10).execute()
        if requests_response.data:
            context['exam_requests'] = [
                {
                    'title': req.get('title', ''),
                    'category': req.get('category', ''),
                    'status': req.get('status', ''),
                    'description': req.get('description', '')
                }
                for req in requests_response.data
            ]
        
        # Get document count for context
        docs_response = supabase.table('exam_documents').select('id').eq('study_id', study_id).eq('user_id', user_id).execute()
        context['document_count'] = len(docs_response.data) if docs_response.data else 0
        
        return context
        
    except Exception as e:
        print(f"Error getting study context: {e}")
        return {}

async def generate_slides_with_gpt5(prompt: str, slide_count: int, audience: str, tone: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate presentation slides using GPT-5"""
    try:
        openai_client = openai_manager.get_client()
        
        # Build context-aware system prompt
        system_prompt = f"""
        You are Oliver, a regulatory compliance AI assistant specializing in creating professional presentations for financial institutions.
        
        Generate a {slide_count}-slide presentation for a {audience} audience with a {tone} tone.
        
        AUDIENCE GUIDELINES:
        - Board: High-level strategic focus, executive summary style, key metrics and outcomes
        - Regulators: Detailed compliance focus, regulatory citations, remediation status
        - Management: Operational focus, action items, resource requirements, timelines
        - Staff: Tactical focus, procedures, training needs, implementation details
        
        TONE GUIDELINES:
        - Formal: Professional language, structured format, regulatory terminology
        - Conversational: Accessible language, engaging format, practical examples
        - Technical: Detailed analysis, specific procedures, technical terminology
        
        SLIDE STRUCTURE:
        - Slide 1: Always a title slide with main topic and key message
        - Middle slides: Content slides with 3-5 bullet points each
        - Last slide: Conclusion with key takeaways and next steps
        
        Return a JSON object with:
        {{
            "title": "Presentation title",
            "description": "Brief description of presentation content",
            "slides": [
                {{
                    "type": "title|content|two-column|conclusion",
                    "title": "Slide title",
                    "content": ["Bullet point 1", "Bullet point 2", ...],
                    "metadata": {{
                        "speakerNotes": "Optional presenter guidance"
                    }}
                }}
            ]
        }}
        
        Focus on regulatory compliance, risk management, and professional business content.
        Make titles declarative and summarize key takeaways.
        Keep bullet points concise but informative.
        """
        
        # Add context if available
        user_prompt = f"Create a presentation about: {prompt}"
        if context and context.get('study_title'):
            user_prompt += f"\n\nContext from study '{context['study_title']}':"
            if context.get('exam_requests'):
                user_prompt += f"\n- {len(context['exam_requests'])} examination requests covering: {', '.join(set(req['category'] for req in context['exam_requests']))}"
            if context.get('document_count', 0) > 0:
                user_prompt += f"\n- {context['document_count']} supporting documents available"
        
        response = await openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            reasoning_effort="medium",
            verbosity="medium"
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Ensure we have the right number of slides
        slides = result.get('slides', [])
        if len(slides) != slide_count:
            # Adjust slide count if needed
            if len(slides) > slide_count:
                slides = slides[:slide_count]
            elif len(slides) < slide_count:
                # Add content slides to reach target count
                for i in range(len(slides), slide_count):
                    slides.append({
                        "type": "content",
                        "title": f"Additional Content {i}",
                        "content": ["Content to be developed", "Based on specific requirements"],
                        "metadata": {}
                    })
        
        # Add unique IDs to slides
        for slide in slides:
            slide['id'] = str(uuid.uuid4())
        
        result['slides'] = slides
        return result
        
    except Exception as e:
        print(f"Error generating slides with GPT-5: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate slides: {str(e)}")

# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/generate", response_model=Dict[str, Any])
async def generate_presentation(
    request: GeneratePresentationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate a new presentation using GPT-5"""
    try:
        # Get study context if requested
        context = {}
        if request.include_context:
            context = await get_study_context(request.study_id, request.user_id)
        
        # Generate slides with GPT-5
        result = await generate_slides_with_gpt5(
            prompt=request.prompt,
            slide_count=request.slide_count,
            audience=request.audience,
            tone=request.tone,
            context=context
        )
        
        # Create presentation response
        presentation_id = str(uuid.uuid4())
        
        # Convert slides to PresentationSlide objects
        slides = [PresentationSlide(**slide) for slide in result.get('slides', [])]
        
        response = {
            "presentation_id": presentation_id,
            "title": result.get('title', 'Generated Presentation'),
            "description": result.get('description', ''),
            "slides": [slide.dict() for slide in slides],
            "metadata": {
                "audience": request.audience,
                "tone": request.tone,
                "generated_at": datetime.utcnow().isoformat(),
                "slide_count": len(slides)
            }
        }
        
        return response
        
    except Exception as e:
        print(f"Error in generate_presentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export")
async def export_presentation(
    request: ExportPresentationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Export presentation as HTML or PDF"""
    try:
        presentation_data = request.presentation_data
        
        if request.format == "html":
            # Generate HTML export
            html_content = generate_html_export(presentation_data)
            
            from fastapi.responses import Response
            return Response(
                content=html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename=\"{presentation_data.get('title', 'presentation').replace(' ', '_')}.html\""
                }
            )
            
        elif request.format == "pdf":
            # Generate PDF export (requires additional setup)
            pdf_content = await generate_pdf_export(presentation_data)
            
            from fastapi.responses import Response
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=\"{presentation_data.get('title', 'presentation').replace(' ', '_')}.pdf\""
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
            
    except Exception as e:
        print(f"Error in export_presentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Export Helper Functions
# ============================================================================

def generate_html_export(presentation_data: Dict[str, Any]) -> str:
    """Generate HTML export of presentation"""
    title = presentation_data.get('title', 'Presentation')
    slides = presentation_data.get('slides', [])
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <link rel="stylesheet" href="/styles/oliver-presentation.css">
        <style>
            .presentation-container {{
                display: flex;
                flex-direction: column;
                gap: 2rem;
                padding: 2rem;
                background: #f8fafc;
            }}
            .slide-container {{
                width: 100%;
                aspect-ratio: 16 / 9;
                display: flex;
                align-items: center;
                justify-content: center;
                page-break-after: always;
            }}
            @media print {{
                .slide-container {{
                    page-break-after: always;
                    height: 100vh;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="presentation-container">
            {generate_slides_html(slides)}
        </div>
        
        <script>
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                const slides = document.querySelectorAll('.slide-container');
                let current = 0;
                
                // Find current slide
                slides.forEach((slide, index) => {{
                    const rect = slide.getBoundingClientRect();
                    if (rect.top <= window.innerHeight / 2 && rect.bottom >= window.innerHeight / 2) {{
                        current = index;
                    }}
                }});
                
                if (e.key === 'ArrowDown' || e.key === 'PageDown') {{
                    e.preventDefault();
                    if (current < slides.length - 1) {{
                        slides[current + 1].scrollIntoView({{ behavior: 'smooth' }});
                    }}
                }} else if (e.key === 'ArrowUp' || e.key === 'PageUp') {{
                    e.preventDefault();
                    if (current > 0) {{
                        slides[current - 1].scrollIntoView({{ behavior: 'smooth' }});
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return html_template

def generate_slides_html(slides: List[Dict[str, Any]]) -> str:
    """Generate HTML for individual slides"""
    slides_html = []
    
    for i, slide in enumerate(slides):
        slide_type = slide.get('type', 'content')
        title = slide.get('title', '')
        content = slide.get('content', [])
        
        if slide_type == 'title':
            slide_html = f"""
            <div class="slide-container">
                <div class="oliver-slide oliver-slide-title">
                    <div class="slide-logo">
                        <img src="/logos/logo2.png" alt="Oliver" />
                    </div>
                    <h1 class="slide-main-title">{title}</h1>
                    <div class="slide-date">{datetime.now().strftime('%B %Y')}</div>
                </div>
            </div>
            """
        elif slide_type == 'conclusion':
            slide_html = f"""
            <div class="slide-container">
                <div class="oliver-slide oliver-slide-content">
                    <div class="slide-header">
                        <h2 class="slide-title">{title}</h2>
                        <div class="slide-logo-header">
                            <img src="/logos/logo2.png" alt="Oliver" />
                        </div>
                    </div>
                    <div class="slide-content-area">
                        <div class="oliver-cta-box">
                            <div class="cta-title">Key Takeaways</div>
                            <ul class="oliver-bullet-list">
                                {''.join(f'<li>{item}</li>' for item in content)}
                            </ul>
                        </div>
                    </div>
                    <div class="oliver-slide-footer">
                        <div class="footer-left">Oliver AI Assistant</div>
                        <div class="footer-center"></div>
                        <div class="footer-right">
                            <span class="slide-number">{i + 1}</span>
                        </div>
                    </div>
                </div>
            </div>
            """
        else:  # content or two-column
            slide_html = f"""
            <div class="slide-container">
                <div class="oliver-slide oliver-slide-content">
                    <div class="slide-header">
                        <h2 class="slide-title">{title}</h2>
                        <div class="slide-logo-header">
                            <img src="/logos/logo2.png" alt="Oliver" />
                        </div>
                    </div>
                    <div class="slide-content-area">
                        <ul class="oliver-bullet-list">
                            {''.join(f'<li>{item}</li>' for item in content)}
                        </ul>
                    </div>
                    <div class="oliver-slide-footer">
                        <div class="footer-left">Oliver AI Assistant</div>
                        <div class="footer-center"></div>
                        <div class="footer-right">
                            <span class="slide-number">{i + 1}</span>
                        </div>
                    </div>
                </div>
            </div>
            """
        
        slides_html.append(slide_html)
    
    return '\n'.join(slides_html)

async def generate_pdf_export(presentation_data: Dict[str, Any]) -> bytes:
    """Generate PDF export of presentation (placeholder - requires additional setup)"""
    # This would require additional dependencies like playwright or weasyprint
    # For now, return a placeholder
    raise HTTPException(status_code=501, detail="PDF export not yet implemented")
