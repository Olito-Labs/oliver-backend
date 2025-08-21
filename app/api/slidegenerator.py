from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any, List
import logging
import dspy

from app.config import settings
from app.models.api import (
    SlideGenerationRequest, 
    SlideGenerationResponse, 
    SlideFramework, 
    SlideExample
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["slides"])


# DSPy Components
class GenerateSlide(dspy.Signature):
    """Generate professional presentation slide HTML from natural language description."""
    
    slide_request = dspy.InputField(desc="Natural language description of the desired slide content and type")
    css_framework = dspy.InputField(desc="CSS framework to use: 'olito-tech' or 'fulton-base'")
    
    slide_html = dspy.OutputField(desc="Complete HTML slide code with proper DOCTYPE, head, and body structure")


class SlideGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateSlide)
    
    def forward(self, slide_request: str, css_framework: str = "olito-tech"):
        # Add framework-specific context to the request
        enhanced_request = self._enhance_request_with_context(slide_request, css_framework)
        
        result = self.generate(
            slide_request=enhanced_request,
            css_framework=css_framework
        )
        
        return dspy.Prediction(slide_html=result.slide_html)
    
    def _enhance_request_with_context(self, request: str, framework: str) -> str:
        """Add framework-specific context and constraints to the user request."""
        
        framework_context = {
            "olito-tech": """
Framework: Olito Tech CSS (olito-tech.css)
Key classes: .of-slide-container, .of-slide, .of-title, .of-subtitle, .of-content-area, .of-decorative-element
Colors: Dark theme with --olito-gold (#c5aa6a), --fulton-blue (#1e4b72), dark backgrounds
Layout: PDF-first design, no animations, rectangular slides
Structure: Container > Slide > Header/Content/Footer
            """,
            "fulton-base": """
Framework: Fulton Base CSS (fulton-base.css)  
Key classes: .fulton-slide-container, .fulton-slide, .slide-title, .fulton-content-area, .fulton-horizontal-layout
Colors: Professional blue palette with --fulton-blue (#1e4b72), --fulton-gold (#c5aa6a)
Layout: Enterprise PDF-optimized, clean typography, grid-based layouts
Structure: Container > Slide > Header/Title/Content/Footnotes
            """
        }
        
        context = framework_context.get(framework, framework_context["olito-tech"])
        
        return f"""
{context}

REQUIREMENTS:
1. Generate complete HTML with DOCTYPE, head, and body
2. Link to correct CSS: ../../framework/css/{framework}.css
3. Use only the framework's CSS classes
4. Create professional, enterprise-appropriate content
5. Ensure PDF-compatible design (no animations, fixed layouts)
6. Include proper semantic HTML structure

USER REQUEST: {request}
        """.strip()


# Global slide generator instance
slide_generator = None

def initialize_dspy():
    """Initialize DSPy with the configured OpenAI model."""
    global slide_generator
    
    try:
        # Format model for DSPy 3.0+ (requires provider/model format)
        model = settings.OPENAI_MODEL
        if "/" not in model:
            model = f"openai/{model}"
        
        # Initialize DSPy LM with model-specific requirements
        if model.endswith("gpt-5") or "gpt-5" in model:
            # GPT-5 requires temperature=1.0 and max_tokens >= 20000
            lm = dspy.LM(
                model=model,
                api_key=settings.OPENAI_API_KEY,
                temperature=1.0,
                max_tokens=20000
            )
        else:
            # Standard models
            lm = dspy.LM(
                model=model,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=settings.MAX_TOKENS
            )
        
        dspy.configure(lm=lm)
        
        # Create slide generator instance
        slide_generator = SlideGenerator()
        
        logger.info(f"DSPy initialized successfully with model: {model}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize DSPy: {e}")
        return False


@router.post("/generate-slide", response_model=SlideGenerationResponse)
async def generate_slide(request: SlideGenerationRequest) -> SlideGenerationResponse:
    """Generate a presentation slide from natural language description."""
    
    # Initialize DSPy if not already done
    if slide_generator is None:
        success = initialize_dspy()
        if not success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to initialize slide generation system"
            )
    
    try:
        logger.info(f"Generating slide: {request.slide_request[:100]}...")
        
        # Generate the slide
        result = slide_generator(
            slide_request=request.slide_request,
            css_framework=request.css_framework
        )
        
        # Prepare response
        response = SlideGenerationResponse(
            slide_html=result.slide_html,
            framework_used=request.css_framework,
            model_used=settings.OPENAI_MODEL,
            generation_metadata={
                "request_length": len(request.slide_request),
                "html_length": len(result.slide_html),
                "framework": request.css_framework
            }
        )
        
        logger.info(f"Slide generated successfully ({len(result.slide_html)} chars)")
        return response
        
    except Exception as e:
        logger.error(f"Slide generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate slide: {str(e)}"
        )


@router.get("/slide-frameworks", response_model=Dict[str, List[SlideFramework]])
async def get_available_frameworks():
    """Get list of available CSS frameworks for slide generation."""
    frameworks = [
        SlideFramework(
            id="olito-tech",
            name="Olito Tech",
            description="Dark theme with gold accents, technical presentations",
            colors={
                "primary": "#c5aa6a",
                "secondary": "#1e4b72",
                "background": "dark"
            }
        ),
        SlideFramework(
            id="fulton-base", 
            name="Fulton Base",
            description="Professional blue palette, enterprise banking slides",
            colors={
                "primary": "#1e4b72",
                "secondary": "#c5aa6a", 
                "background": "light"
            }
        )
    ]
    
    return {"frameworks": frameworks}


@router.get("/slide-examples", response_model=Dict[str, List[SlideExample]])
async def get_slide_examples():
    """Get example slide requests for different types of slides."""
    examples = [
        SlideExample(
            type="title",
            request="Create a title slide for 'AI-Powered Banking Solutions' with subtitle 'Transforming Financial Services'",
            description="Hero slide with main title and subtitle"
        ),
        SlideExample(
            type="metrics",
            request="Make a slide showing 3 key metrics: $2.4M savings, 60% faster processing, 95% accuracy",
            description="Metrics dashboard with key performance indicators"
        ),
        SlideExample(
            type="problem",
            request="Create a problem slide about data integration challenges in banking mergers",
            description="Problem statement slide highlighting key challenges"
        ),
        SlideExample(
            type="solution",
            request="Generate a solution slide with 3 AI-powered tools for regulatory compliance",
            description="Solution overview with multiple components"
        ),
        SlideExample(
            type="architecture",
            request="Show technical architecture with agent workflow for regulatory analysis",
            description="Technical diagram slide with system components"
        )
    ]
    
    return {"examples": examples}


# Health check for slide generation system
@router.get("/slide-health")
async def slide_generation_health():
    """Check if slide generation system is healthy."""
    try:
        # Test DSPy initialization
        if slide_generator is None:
            initialize_dspy()
        
        # Basic health check
        health_status = {
            "status": "healthy" if slide_generator is not None else "unhealthy",
            "dspy_configured": slide_generator is not None,
            "model": settings.OPENAI_MODEL,
            "frameworks_available": ["olito-tech", "fulton-base"]
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Slide generation health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "dspy_configured": False
        }
