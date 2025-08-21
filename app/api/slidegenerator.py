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


# DSPy Components - Enhanced Professional Slide Generation

class AnalyzeSlideLayout(dspy.Signature):
    """Analyze slide request to determine optimal layout pattern and content structure."""
    
    slide_request: str = dspy.InputField(desc="Natural language description of the desired slide content and purpose")
    
    layout_type: str = dspy.OutputField(desc="Layout pattern: 'foundation_pillars', 'process_flow', 'three_column', 'metrics_grid', 'title_only', 'narrative_flow'")
    content_elements: list[str] = dspy.OutputField(desc="Key content elements to include (titles, data points, sections)")
    visual_emphasis: str = dspy.OutputField(desc="Primary visual focus area and hierarchy")
    slide_purpose: str = dspy.OutputField(desc="Main purpose: introduce, explain, demonstrate, compare, conclude")

class ProfessionalSlideGenerator(dspy.Signature):
    """Generate professional 16:9 landscape presentation slides using olito-tech CSS framework.
    
    DESIGN REQUIREMENTS:
    - 16:9 landscape format optimized for professional presentations
    - Use olito-tech.css framework classes and design system
    - Left-aligned titles using .slide-title class (2.85rem, bold, gold)
    - Effective use of horizontal space in landscape orientation
    - Consistent header with dual logos (top-right positioning)
    - Decorative gold gradient elements (top and bottom)
    - Professional enterprise aesthetic with dark theme
    
    LAYOUT PATTERNS AVAILABLE:
    - foundation_pillars: Side-by-side content blocks with connecting elements
    - process_flow: Horizontal sequence with arrows/connectors  
    - three_column: Agents → Orchestration → Workflows grid
    - metrics_grid: Data visualization with cards/panels
    - title_only: Centered title slide format
    - narrative_flow: Vertical content progression with visual hierarchy
    
    CSS FRAMEWORK CONTEXT:
    - Required structure: .of-slide-container → .of-slide → .content-main
    - Header: .content-header (top-right dual logos)
    - Decorative: .of-decorative-element (top), .of-decorative-bottom
    - Typography: .slide-title (main), .slide-subtitle (secondary)
    - Components: .foundation-pillar, .agent-card, .workflow-card
    - Colors: --olito-gold (#c5aa6a), --panel-dark (#122743), --fulton-white
    """
    
    slide_request: str = dspy.InputField(desc="Enhanced slide request with layout and design context")
    layout_type: str = dspy.InputField(desc="Determined layout pattern for the slide")
    content_elements: list[str] = dspy.InputField(desc="Key content elements to structure")
    css_framework: str = dspy.InputField(desc="CSS framework: 'olito-tech'")
    
    slide_html: str = dspy.OutputField(desc="Complete HTML slide with proper DOCTYPE, olito-tech.css link, and landscape-optimized layout")


class SlideGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        # Multi-stage pipeline for better slide generation
        self.layout_analyzer = dspy.ChainOfThought(AnalyzeSlideLayout)
        self.slide_generator = dspy.ChainOfThought(ProfessionalSlideGenerator)
    
    def forward(self, slide_request: str, css_framework: str = "olito-tech"):
        # Stage 1: Analyze the request to determine layout and structure
        analysis = self.layout_analyzer(slide_request=slide_request)
        
        # Stage 2: Generate enhanced request with CSS framework context
        enhanced_request = self._create_enhanced_request(
            slide_request, 
            analysis.layout_type, 
            analysis.content_elements,
            css_framework
        )
        
        # Stage 3: Generate the final slide HTML
        result = self.slide_generator(
            slide_request=enhanced_request,
            layout_type=analysis.layout_type,
            content_elements=analysis.content_elements,
            css_framework=css_framework
        )
        
        return dspy.Prediction(
            slide_html=result.slide_html,
            layout_type=analysis.layout_type,
            content_elements=analysis.content_elements,
            slide_purpose=analysis.slide_purpose
        )
    
    def _create_enhanced_request(self, request: str, layout_type: str, content_elements: list, framework: str) -> str:
        """Create enhanced request with CSS framework context and layout patterns."""
        
        # Get CSS framework context
        css_context = self._get_css_framework_context()
        
        # Get layout-specific guidance
        layout_guidance = self._get_layout_guidance(layout_type)
        
        # Get pattern examples based on layout type
        pattern_examples = self._get_pattern_examples(layout_type)
        
        return f"""
{css_context}

{layout_guidance}

LAYOUT TYPE: {layout_type}
CONTENT ELEMENTS: {', '.join(content_elements)}

{pattern_examples}

STRICT REQUIREMENTS:
1. Generate complete HTML with DOCTYPE, head, and body
2. Link to CSS: ../../framework/css/{framework}.css  
3. Use ONLY olito-tech.css framework classes
4. 16:9 landscape format with effective horizontal space usage
5. Left-aligned titles using .slide-title class (2.85rem, bold, gold)
6. Include .content-header with dual logos (top-right)
7. Add .of-decorative-element (top) and .of-decorative-bottom
8. Professional enterprise aesthetic, PDF-compatible (no animations)
9. Proper semantic HTML structure with accessibility

USER REQUEST: {request}
        """.strip()
    
    def _get_css_framework_context(self) -> str:
        """Get comprehensive CSS framework context."""
        return """
OLITO-TECH CSS FRAMEWORK GUIDE:

REQUIRED STRUCTURE:
- Container: .of-slide-container → .of-slide → .content-main
- Header: .content-header (top-right, dual logos with Olito + Fulton)
- Decorative: .of-decorative-element (top), .of-decorative-bottom
- Footnotes: .of-footnotes (bottom-anchored)

KEY CLASSES:
- .slide-title: Main title (2.85rem, bold, --olito-gold, left-aligned)
- .slide-subtitle: Subtitle (1.05rem, #9fb3c8, left-aligned)
- .foundation-pillar: Content blocks with gold borders and gradients
- .agent-card: Bordered cards with left accent colors
- .workflow-card: Horizontal cards with assembly indicators
- .narrative-flow: Vertical content progression container
- .success-foundation: Grid layout for pillar-style content

LAYOUT SYSTEMS:
- .solution-grid: 3-column grid (28% 14% 1fr) for complex layouts
- .narrative-flow: Vertical flow with centered alignment
- .cycle-stages-container: Horizontal process flow with connectors

COLORS & VARIABLES:
- Primary: var(--olito-gold) #c5aa6a
- Background: var(--panel-dark) #122743  
- Text: var(--fulton-white) #ffffff
- Muted: #9fb3c8, #cbd5e1
- Spacing: var(--spacing-xs) to var(--spacing-3xl)
        """
    
    def _get_layout_guidance(self, layout_type: str) -> str:
        """Get specific guidance for the determined layout type."""
        guidance = {
            "foundation_pillars": """
FOUNDATION PILLARS LAYOUT:
- Use .success-foundation with grid layout
- Create .foundation-pillar blocks with connecting elements
- Include .foundation-plus connector between pillars
- Each pillar has .pillar-icon with .icon-circle and .pillar-text
- Emphasize horizontal relationship between concepts
            """,
            "process_flow": """
PROCESS FLOW LAYOUT:
- Use .cycle-stages-container for horizontal sequence
- Create .stage elements with .stage-icon and descriptions
- Add CSS ::after pseudo-elements for connecting arrows
- Show progression from left to right across the slide
- Include .mechanism-panel wrapper for visual grouping
            """,
            "three_column": """
THREE COLUMN LAYOUT:
- Use .solution-grid with 28% 14% 1fr columns
- Left: agents/components list, Center: orchestration, Right: workflows
- Include .column-header for each section
- Use .agent-card, .engine-hub, .workflow-card components
- Show relationship flow from left to right
            """,
            "narrative_flow": """
NARRATIVE FLOW LAYOUT:
- Use .narrative-flow container for vertical progression
- Include .premise, .mechanism-panel, .problem-hook sections
- Center-align content with max-width constraints
- Build logical argument from top to bottom
- Use visual hierarchy to guide reader attention
            """,
            "title_only": """
TITLE SLIDE LAYOUT:
- Add .of-title-slide class to .of-slide
- Center all content vertically and horizontally
- Use .of-title-area wrapper for title content
- Include .of-dual-logos for brand presentation
- Keep layout simple and impactful
            """,
            "metrics_grid": """
METRICS GRID LAYOUT:
- Create grid of metric cards or data visualizations
- Use consistent spacing and alignment
- Highlight key numbers with larger typography
- Include context and labels for each metric
- Maintain visual balance across the grid
            """
        }
        return guidance.get(layout_type, guidance["narrative_flow"])
    
    def _get_pattern_examples(self, layout_type: str) -> str:
        """Get pattern examples based on your existing slides."""
        examples = {
            "foundation_pillars": """
PATTERN EXAMPLE (Foundation Pillars):
<div class="success-foundation">
  <div class="foundation-pillar">
    <div class="pillar-icon"><div class="icon-circle"><svg>...</svg></div></div>
    <div class="pillar-text">
      <h3>Pillar Title</h3>
      <p>Description text</p>
    </div>
  </div>
  <div class="foundation-plus">+</div>
  <div class="foundation-pillar">...</div>
</div>
            """,
            "process_flow": """
PATTERN EXAMPLE (Process Flow):
<div class="mechanism-panel">
  <h3>Process Title</h3>
  <div class="cycle-stages-container">
    <div class="stage">
      <div class="stage-icon"><svg>...</svg></div>
      <p class="stage-name">Stage Name</p>
      <p class="stage-cost">Resource Impact</p>
    </div>
    <!-- More stages with CSS arrows -->
  </div>
</div>
            """,
            "three_column": """
PATTERN EXAMPLE (Three Column):
<div class="solution-grid">
  <div class="agents-column">
    <div class="column-header">1. Components</div>
    <div class="agents-list">
      <div class="agent-card" style="--agent-color: #1e4b72;">
        <div class="agent-icon">IC</div>
        <div class="agent-content">
          <div class="agent-title">Component Name</div>
          <div class="agent-description">Description</div>
        </div>
      </div>
    </div>
  </div>
  <div class="engine-column">
    <div class="column-header">2. Process</div>
    <div class="engine-hub">...</div>
  </div>
  <div class="workflows-column">
    <div class="column-header">3. Outputs</div>
    <div class="workflow-card">...</div>
  </div>
</div>
            """
        }
        return examples.get(layout_type, "")


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
        
        # Prepare response with enhanced metadata
        response = SlideGenerationResponse(
            slide_html=result.slide_html,
            framework_used=request.css_framework,
            model_used=settings.OPENAI_MODEL,
            generation_metadata={
                "request_length": len(request.slide_request),
                "html_length": len(result.slide_html),
                "framework": request.css_framework,
                "layout_type": result.layout_type,
                "content_elements": result.content_elements,
                "slide_purpose": result.slide_purpose,
                "stages_completed": ["layout_analysis", "content_structuring", "html_generation"],
                "pipeline_version": "enhanced_v1"
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
    """Get example slide requests for different layout patterns."""
    examples = [
        SlideExample(
            type="title_only",
            request="Create a title slide for 'AI-Powered Banking Solutions' with subtitle 'Transforming Financial Services Through Innovation'",
            description="Hero slide with centered title and subtitle (title_only layout)"
        ),
        SlideExample(
            type="foundation_pillars",
            request="Show Fulton Bank's growth foundation with two reinforcing pillars: internal transformation and strategic expansion",
            description="Side-by-side content blocks with connecting elements (foundation_pillars layout)"
        ),
        SlideExample(
            type="process_flow",
            request="Explain the regulatory supervision cycle showing planning, activities, communication, and documentation stages",
            description="Horizontal sequence with arrows showing process flow (process_flow layout)"
        ),
        SlideExample(
            type="three_column",
            request="Introduce Oliver with AI agents, orchestration engine, and custom workflows for regulatory compliance",
            description="Three-column layout showing components, process, and outputs (three_column layout)"
        ),
        SlideExample(
            type="narrative_flow",
            request="Present the regulatory challenge: growth attracts scrutiny, creating resource strain and focus diversion",
            description="Vertical content progression building an argument (narrative_flow layout)"
        ),
        SlideExample(
            type="metrics_grid",
            request="Display key performance metrics: $2.4M cost savings, 60% faster processing, 95% accuracy improvement, 40% reduction in manual work",
            description="Grid of metric cards with data visualization (metrics_grid layout)"
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
