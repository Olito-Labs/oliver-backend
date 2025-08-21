from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any, List
import logging
import dspy
import json

from app.config import settings
from app.models.api import (
    SlideGenerationRequest, 
    SlideGenerationResponse, 
    SlideFramework, 
    SlideExample
)
from app.slide_templates import SLIDE_TEMPLATES, VISUAL_COMPONENTS, SVG_ICONS

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["slides"])


# DSPy Components
class GenerateSlide(dspy.Signature):
    """Generate visually sophisticated, McKinsey/BCG-quality presentation slide HTML."""
    
    slide_request = dspy.InputField(desc="Natural language description of the desired slide content and type")
    css_framework = dspy.InputField(desc="CSS framework to use: 'olito-tech' or 'fulton-base'")
    visual_examples = dspy.InputField(desc="Examples of high-quality slide patterns and visual techniques")
    design_principles = dspy.InputField(desc="Core design principles for professional presentations")
    
    slide_html = dspy.OutputField(desc="Complete HTML slide code with sophisticated visual design, proper structure, and professional styling")


class SlideGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateSlide)
        self.visual_examples = self._load_visual_examples()
        self.design_principles = self._load_design_principles()
    
    def forward(self, slide_request: str, css_framework: str = "olito-tech"):
        # Add framework-specific context to the request
        enhanced_request = self._enhance_request_with_context(slide_request, css_framework)
        
        result = self.generate(
            slide_request=enhanced_request,
            css_framework=css_framework,
            visual_examples=self.visual_examples[css_framework],
            design_principles=self.design_principles
        )
        
        return dspy.Prediction(slide_html=result.slide_html)
    
    def _enhance_request_with_context(self, request: str, framework: str) -> str:
        """Add framework-specific context and visual design requirements."""
        
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

VISUAL DESIGN REQUIREMENTS:
1. Create VISUALLY SOPHISTICATED slides like McKinsey/BCG presentations
2. Use GRAPHICAL ELEMENTS: icons, shapes, visual hierarchies, cards, grids
3. Implement PROFESSIONAL LAYOUTS: multi-column, visual flow diagrams, comparison matrices
4. Apply VISUAL STORYTELLING: use spacing, typography, and color to guide the eye
5. Include CUSTOM STYLING in <style> tags for unique visual effects
6. Create INFORMATION HIERARCHY with varied font sizes, weights, and colors
7. Use DATA VISUALIZATION techniques even for conceptual information
8. Add VISUAL METAPHORS and iconography (using SVG icons or Unicode symbols)

HTML STRUCTURE:
1. Complete HTML with DOCTYPE, head, and body
2. Link to CSS: ../../framework/css/{framework}.css
3. Include comprehensive <style> section for custom visual design
4. Use semantic HTML with proper ARIA labels
5. Implement responsive design with media queries

USER REQUEST: {request}
        """.strip()


    def _load_visual_examples(self) -> dict:
        """Load examples of high-quality visual slide patterns."""
        return {
            "olito-tech": """
VISUAL PATTERN EXAMPLES:

1. MULTI-COLUMN LAYOUTS WITH VISUAL DIVIDERS:
   <div class="intro-grid" style="display: grid; grid-template-columns: 1fr 2px 1fr; gap: 2rem;">
     <div class="left-section">...</div>
     <div class="gold-divider" style="background: linear-gradient(180deg, transparent 20%, var(--olito-gold) 35%, var(--olito-gold) 65%, transparent 80%); width: 2px;"></div>
     <div class="right-section">...</div>
   </div>

2. VISUAL CARDS WITH HOVER EFFECTS:
   <div class="horizon-card" style="background: rgba(255,255,255,0.04); border: 2px solid var(--olito-gold); border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: transform 0.2s;">
     <div class="card-header" style="display: flex; align-items: center; gap: 0.5rem;">
       <div class="icon-circle" style="width: 32px; height: 32px; background: var(--olito-gold); border-radius: 50%; display: grid; place-items: center;">1</div>
       <h3 style="color: white; font-weight: 600;">Title</h3>
     </div>
   </div>

3. PROCESS FLOW WITH ARROWS:
   <div class="cycle-stages" style="display: flex; justify-content: space-between;">
     <div class="stage" style="position: relative;">
       <div class="stage-icon" style="width: 64px; height: 64px; border-radius: 50%; background: linear-gradient(135deg, rgba(197,170,106,0.1), transparent); border: 1px solid var(--olito-gold);">
         <!-- SVG icon here -->
       </div>
       <p class="stage-name">Stage Name</p>
       <!-- Arrow connector using ::after pseudo-element or inline SVG -->
     </div>
   </div>

4. VISUAL HIERARCHY WITH TYPOGRAPHY:
   <h1 style="font-size: 2.5rem; font-weight: 700; color: var(--olito-gold); margin-bottom: 0.5rem;">Main Title</h1>
   <h2 style="font-size: 1.25rem; color: #9fb3c8; margin-bottom: 2rem;">Supporting subtitle with context</h2>
   <div class="content-panels">...</div>

5. DATA VISUALIZATION PATTERNS:
   - Use grids for comparisons: grid-template-columns for equal columns
   - Use flexbox for dynamic layouts: display: flex with gap
   - Create visual metrics with large numbers and supporting text
   - Use progress bars, circles, or custom shapes for data representation
            """,
            "fulton-base": """
VISUAL PATTERN EXAMPLES:

1. ENTERPRISE GRID LAYOUTS:
   <div class="metrics-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem;">
     <div class="metric-card" style="background: white; border-left: 4px solid var(--fulton-blue); padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
       <div class="metric-value" style="font-size: 2.5rem; font-weight: 700; color: var(--fulton-blue);">$2.4M</div>
       <div class="metric-label" style="color: #666; font-size: 0.9rem; text-transform: uppercase;">Annual Savings</div>
     </div>
   </div>

2. COMPARISON MATRICES:
   <table class="comparison-table" style="width: 100%; border-collapse: separate; border-spacing: 0;">
     <thead style="background: var(--fulton-blue); color: white;">
       <tr><th>Criteria</th><th>Option A</th><th>Option B</th></tr>
     </thead>
     <tbody>
       <tr style="background: rgba(30,75,114,0.05);">...</tr>
     </tbody>
   </table>

3. PROFESSIONAL CALLOUT BOXES:
   <div class="insight-box" style="background: linear-gradient(135deg, rgba(30,75,114,0.1), transparent); border-left: 3px solid var(--fulton-gold); padding: 1.5rem; margin: 2rem 0;">
     <h3 style="color: var(--fulton-blue); margin-bottom: 0.5rem;">Key Insight</h3>
     <p style="color: #333; line-height: 1.6;">Important finding or recommendation...</p>
   </div>
            """
        }
    
    def _load_design_principles(self) -> str:
        """Load core design principles for professional presentations."""
        return """
CORE DESIGN PRINCIPLES FOR PROFESSIONAL SLIDES:

1. VISUAL HIERARCHY:
   - Use size, color, and weight to establish clear importance levels
   - Primary: Large, bold, branded colors (gold/blue)
   - Secondary: Medium size, semi-bold, white/light colors  
   - Supporting: Smaller, regular weight, muted colors

2. WHITESPACE & BREATHING ROOM:
   - Use generous padding (1.5-2rem minimum)
   - Create visual separation between sections
   - Don't fill every pixel - emptiness is powerful

3. VISUAL STORYTELLING:
   - Guide the eye with visual flow (left-to-right, top-to-bottom)
   - Use arrows, lines, or numbered sequences for processes
   - Group related content in visual containers (cards, panels)

4. PROFESSIONAL COLOR USAGE:
   - Primary brand color for emphasis and headers
   - Neutral grays for body text
   - Accent colors sparingly for highlights
   - Consistent opacity/transparency for depth

5. TYPOGRAPHY EXCELLENCE:
   - Limit to 2-3 font sizes per slide
   - Use weight variations (300-700) for hierarchy
   - Consistent line-height (1.4-1.6 for body, 1.1-1.2 for headers)

6. VISUAL ELEMENTS:
   - Icons to represent concepts (SVG or Unicode)
   - Shapes for grouping (rounded rectangles, circles)
   - Lines/dividers for separation (with gradient effects)
   - Shadows for depth (subtle, not harsh)

7. RESPONSIVE & ACCESSIBLE:
   - Use relative units (rem, %, vw/vh)
   - Include media queries for different screen sizes
   - Proper contrast ratios (WCAG AA minimum)
   - Semantic HTML with ARIA labels

8. CONSULTING-STYLE TECHNIQUES:
   - 2x2 matrices for strategic positioning
   - Process flows with clear stages
   - Comparison tables with visual indicators
   - Metric dashboards with large numbers
   - Executive summary boxes with key takeaways
        """

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
        
        # Detect slide type from request
        slide_type = detect_slide_type(request.slide_request)
        logger.info(f"Detected slide type: {slide_type}")
        
        # Generate the slide with enhanced context
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
                "framework": request.css_framework,
                "detected_type": slide_type
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

def detect_slide_type(request: str) -> str:
    """Detect the type of slide from the request."""
    request_lower = request.lower()
    
    if any(word in request_lower for word in ['title', 'hero', 'intro', 'cover']):
        return 'title_slide'
    elif any(word in request_lower for word in ['compare', 'comparison', 'versus', 'options', 'three']):
        return 'three_column_comparison'
    elif any(word in request_lower for word in ['process', 'flow', 'steps', 'stages', 'workflow']):
        return 'process_flow'
    elif any(word in request_lower for word in ['metrics', 'kpi', 'dashboard', 'numbers', 'statistics']):
        return 'metrics_dashboard'
    elif any(word in request_lower for word in ['problem', 'solution', 'challenge', 'opportunity']):
        return 'problem_solution'
    elif any(word in request_lower for word in ['summary', 'executive', 'takeaway', 'conclusion']):
        return 'executive_summary'
    elif any(word in request_lower for word in ['matrix', '2x2', 'quadrant', 'positioning']):
        return 'matrix_2x2'
    else:
        return 'general'


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
            request="Create a visually stunning title slide for 'AI-Powered Risk Management Solutions' with subtitle 'Three enterprise tools to anticipate, detect, and mitigate risk'",
            description="Hero slide with strong visual impact and professional typography"
        ),
        SlideExample(
            type="three_column",
            request="Create a three-column comparison slide showing: 1) Predictive Loss Forecasting Engine with scenario simulation, 2) Continuous Control Monitoring Copilot with LLM pattern recognition, 3) Third-Party Risk Intelligence Radar with vendor scoring",
            description="Professional three-column layout with visual cards and hover effects"
        ),
        SlideExample(
            type="process_flow",
            request="Show the regulatory exam cycle with 4 stages: Planning (Senior Management Time), Activities (Team Hours), Communication (Executive Focus), Documentation (Compliance Resources) - with visual flow arrows between stages",
            description="Visual process flow with circular icons and gradient connectors"
        ),
        SlideExample(
            type="metrics",
            request="Create a metrics dashboard showing: $2.4M annual savings (up 150%), 60% faster processing time, 95% accuracy rate, 3x productivity gain - with visual indicators and trend arrows",
            description="Metrics dashboard with large numbers, visual emphasis, and change indicators"
        ),
        SlideExample(
            type="problem_solution",
            request="Create a problem-solution slide: Problem side shows 'Manual processes, High error rates, Compliance risks' with red warning icons. Solution side shows 'AI automation, 95% accuracy, Real-time monitoring' with green success icons",
            description="Visual contrast between problem (red) and solution (green) with icons"
        ),
        SlideExample(
            type="executive_summary",
            request="Generate an executive summary with 3 key takeaways: 1) AI reduces operational risk by 40%, 2) ROI achieved in 6 months, 3) Scalable across all business units. Include a bottom line statement about transformational impact",
            description="Executive summary with numbered points and visual hierarchy"
        ),
        SlideExample(
            type="matrix",
            request="Create a 2x2 matrix for strategic positioning: X-axis is 'Implementation Complexity' (Low to High), Y-axis is 'Business Impact' (Low to High). Place items in quadrants with visual styling",
            description="Strategic 2x2 matrix with labeled axes and styled quadrants"
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
