from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any, List
import logging
import dspy
import json
import hashlib
from functools import lru_cache

from app.config import settings
from app.llm_providers import openai_manager
from app.models.api import (
    SlideGenerationRequest, 
    SlideGenerationResponse, 
    SlideFramework, 
    SlideExample
)
from app.slide_templates import SLIDE_TEMPLATES, VISUAL_COMPONENTS, SVG_ICONS
from app.refined_slide_patterns import REFINED_PATTERNS, DESIGN_GUIDELINES, ANTI_PATTERNS, get_pattern_for_request
from app.synthesis_prompts import get_synthesis_context

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["slides"])


# DSPy Components - Optimized for speed and quality
class AnalyzeAndStructure(dspy.Signature):
    """Analyze request and structure professional slide content in one pass.
    
    FAST ANALYSIS:
    1. Identify the core message and supporting points
    2. Determine the best visual pattern (executive summary, data insight, comparison)
    3. Structure 2-3 main content sections with appropriate depth
    4. Specify any data visualizations needed
    
    Be comprehensive but efficient - professional slides need substance.
    """
    
    user_request = dspy.InputField(desc="User's slide request")
    
    slide_title = dspy.OutputField(desc="Declarative title (≤15 words) capturing the key insight")
    slide_subtitle = dspy.OutputField(desc="Supporting context or framing")
    slide_pattern = dspy.OutputField(desc="Pattern: 'executive_summary' | 'data_insight' | 'comparison' | 'three_column' | 'focused'")
    main_sections = dspy.OutputField(desc="2-3 main sections as JSON: [{title, content, points}]")
    visual_elements = dspy.OutputField(desc="Visuals needed: 'metrics' | 'gauge' | 'comparison_panels' | 'none'")
    key_data = dspy.OutputField(desc="Key metrics/percentages to highlight")

class GenerateProfessionalHTML(dspy.Signature):
    """Generate rich, professional HTML slide efficiently.
    
    Create complete HTML that:
    - Uses sophisticated layouts matching the pattern
    - Includes visual elements (metrics, panels, etc.)
    - Follows McKinsey/BCG design standards
    - Has proper spacing, typography, and hierarchy
    - Typically 200-350 lines of well-structured HTML
    """
    
    slide_title = dspy.InputField(desc="Slide title")
    slide_subtitle = dspy.InputField(desc="Subtitle/context")
    slide_pattern = dspy.InputField(desc="Visual pattern to follow")
    main_sections = dspy.InputField(desc="Content sections")
    visual_elements = dspy.InputField(desc="Visual components needed")
    key_data = dspy.InputField(desc="Metrics and data points")
    css_framework = dspy.InputField(desc="'olito-tech' or 'fulton-base'")
    design_guidelines = dspy.InputField(desc="Key design principles")
    
    slide_html = dspy.OutputField(desc="Complete professional HTML with rich visuals and layout")


class OptimizedSlideGenerator(dspy.Module):
    """Fast, two-stage slide generator for professional slides."""
    
    def __init__(self):
        super().__init__()
        # Two-stage pipeline for speed
        # Use Predict instead of ChainOfThought for 2-3x speed improvement
        self.analyzer = dspy.Predict(AnalyzeAndStructure)
        self.html_generator = dspy.Predict(GenerateProfessionalHTML)
        
        # Pre-load templates for faster access
        self.pattern_cache = self._preload_patterns()
        self.design_cache = self._preload_design_guidelines()
        
        # Simple cache for recent generations
        self._cache = {}
        self._cache_size = 10
    
    def forward(self, slide_request: str, css_framework: str = "olito-tech"):
        # Check cache first
        cache_key = hashlib.md5(f"{slide_request}:{css_framework}".encode()).hexdigest()
        if cache_key in self._cache:
            logger.info("Using cached result for speed")
            return self._cache[cache_key]
        
        # Stage 1: Analyze and structure in one pass (faster)
        logger.info(f"Analyzing and structuring: {slide_request[:100]}...")
        analysis = self.analyzer(
            user_request=slide_request
        )
        logger.info(f"Pattern: {analysis.slide_pattern}, generating HTML...")
        
        # Stage 2: Generate HTML with cached guidelines
        design_guidelines = self._get_cached_guidelines(analysis.slide_pattern, css_framework)
        
        html_result = self.html_generator(
            slide_title=analysis.slide_title,
            slide_subtitle=analysis.slide_subtitle,
            slide_pattern=analysis.slide_pattern,
            main_sections=analysis.main_sections,
            visual_elements=analysis.visual_elements,
            key_data=analysis.key_data,
            css_framework=css_framework,
            design_guidelines=design_guidelines
        )
        
        # Quick post-processing
        final_html = self._quick_enhance(html_result.slide_html, analysis.visual_elements)
        logger.info(f"Generated slide ({len(final_html)} chars)")
        
        result = dspy.Prediction(
            slide_html=final_html,
            slide_pattern=analysis.slide_pattern,
            primary_message=analysis.slide_title,
            metadata={
                "pattern": analysis.slide_pattern,
                "visual_elements": analysis.visual_elements
            }
        )
        
        # Cache result
        if len(self._cache) >= self._cache_size:
            # Remove oldest entry
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = result
        
        return result

    # ---------- Optimized Helper Methods ----------
    
    def _preload_patterns(self) -> dict:
        """Pre-load pattern examples for faster access."""
        return {
            "executive_summary": "2-column grid with headline and insights panels",
            "data_insight": "Visualization left, insights right in 2-column layout",
            "comparison": "Side-by-side panels with visual distinction",
            "three_column": "3 equal columns with consistent treatment",
            "focused": "Large title with minimal supporting elements"
        }
    
    def _preload_design_guidelines(self) -> dict:
        """Pre-load concise design guidelines for speed."""
        return {
            "olito-tech": """
            CSS: olito-tech.css | Colors: --olito-gold (#c5aa6a), dark theme
            Typography: 2.85rem titles, 1.8rem sections, 1.1rem panels
            Spacing: 2-3rem padding, 1.5-2rem gaps
            Panels: rgba(255,255,255,0.04) backgrounds, 1px borders
            """,
            "fulton-base": """
            CSS: fulton-base.css | Colors: --fulton-blue (#1e4b72), light theme  
            Typography: Professional hierarchy, clean fonts
            Spacing: Generous whitespace, grid layouts
            Panels: Clean cards with accent borders
            """
        }
    
    def _get_cached_guidelines(self, pattern: str, framework: str) -> str:
        """Get cached guidelines for fast generation."""
        base = self.design_cache.get(framework, self.design_cache["olito-tech"])
        pattern_hint = self.pattern_cache.get(pattern, "")
        
        # Minimal but effective guidelines
        return f"""
{base}

PATTERN: {pattern} - {pattern_hint}

KEY REQUIREMENTS:
1. Professional HTML (200-350 lines)
2. Proper slide structure with title, subtitle, main content
3. {pattern} layout pattern
4. Include headers with logos if olito-tech
5. Add timestamp at bottom-right
6. Use CSS Grid for layouts
7. Rich visual elements where appropriate

EXAMPLE STRUCTURE:
<!DOCTYPE html>
<html>
<head>
  <title>{{title}}</title>
  <link rel="stylesheet" href="../../framework/css/{framework}.css" />
  <style>/* Professional styles */</style>
</head>
<body>
  <div class="of-slide-container">
    <div class="of-slide">
      <!-- Header with logos -->
      <h1 class="slide-title">{{title}}</h1>
      <div class="slide-subtitle">{{subtitle}}</div>
      <!-- Main content with {pattern} layout -->
      <div class="timestamp-br">Generated {{date}}</div>
    </div>
  </div>
</body>
</html>
"""
    
    def _quick_enhance(self, html: str, visual_elements: str) -> str:
        """Quick HTML enhancement without heavy processing."""
        import datetime
        
        # Add timestamp if missing
        if "timestamp-br" not in html:
            timestamp = datetime.datetime.now().strftime("%b %d, %Y • %H:%M EST")
            timestamp_html = f'<div class="timestamp-br">Generated {timestamp}</div>'
            html = html.replace("</body>", f"      {timestamp_html}\n    </body>")
        
        # Quick visual element injection if needed
        if "metric" in visual_elements and "metric-card" not in html:
            # Inject a simple metric template if metrics are needed but missing
            pass  # Skip complex processing for speed
        
        return html
    
    def _get_pattern_examples(self, pattern: str, framework: str) -> str:
        """Get HTML examples for the specific pattern from our high-quality slides."""
        
        # These are based on the WSFS analysis slides which are exemplary
        pattern_examples = {
            "executive_summary": """
            Example structure from professional slides:
            - Headline section with gradient background and strong message
            - 2-column analysis grid comparing perspectives (e.g., Surface View vs Deeper Insight)
            - Bottom section with prediction and opportunity panels
            - Rich typography: 2.85rem titles, 1.8rem section headers, strategic colors
            - Professional spacing: 2-3rem padding, 1.5-2rem gaps
            """,
            
            "data_insight": """
            Example structure:
            - 2-column layout: visualization left (gauge/chart), insights right
            - Gauge with SVG visualization showing thresholds
            - Metric cards with large values and context
            - 3-4 insight panels with icons and focused content
            - Source attribution at bottom
            """,
            
            "strategic_comparison": """
            Example structure:
            - Clear title focusing on the transformation
            - 2 equal panels side-by-side with visual distinction
            - Each panel: icon header, title, 3-4 key points
            - Color coding: different accent colors for each side
            - Optional implications section below
            """,
            
            "three_pillar": """
            Example structure:
            - 3-column grid with equal spacing
            - Each column: large number/icon, title, subtitle, description
            - Consistent visual treatment across columns
            - Optional metrics or indicators per column
            - Generous whitespace between elements
            """,
            
            "focused_message": """
            Example structure:
            - Large impactful title (2.5-3rem)
            - Supporting subtitle for context
            - Optional single visual element (metric/chart)
            - 2-3 supporting points maximum
            - Extensive whitespace for emphasis
            """
        }
        
        return pattern_examples.get(pattern, pattern_examples["focused_message"])
    
    def _enhance_html(self, html: str, visual_requirements: str) -> str:
        """Enhance HTML with visual components based on requirements."""
        
        # Add timestamp
        if "timestamp-br" not in html:
            import datetime
            timestamp = datetime.datetime.now().strftime("%b %d, %Y • %H:%M EST")
            timestamp_html = f'\n      <div class="timestamp-br">Generated {timestamp}</div>'
            html = html.replace("</body>", f"{timestamp_html}\n</body>")
        
        # Add decorative elements if missing
        if "of-decorative-element" not in html and "of-slide" in html:
            decorative = '<div class="of-decorative-element"></div>'
            html = html.replace('<div class="of-slide">', f'<div class="of-slide">\n      {decorative}')
        
        # Ensure proper headers with logos (based on WSFS examples)
        if "content-header" not in html and "olito-tech" in html:
            header_html = """
      <div class="content-header">\n        <img class="header-brain" src="../../framework/assets/logo2.png" alt="Olito Labs Brain" />\n        <img class="header-wordmark" src="../../framework/assets/logo3.png" alt="Olito Labs" />\n      </div>"""
            html = html.replace('<div class="content-main">', f'{header_html}\n\n      <div class="content-main">')
        
            return html
    



    def _load_pattern_examples(self) -> dict:
        """Load refined examples based on high-quality slide analysis."""
        return {
            "olito-tech": """
REFINED VISUAL PATTERNS (Based on WSFS/Tech Architecture Analysis):

1. EXECUTIVE SUMMARY LAYOUT (WSFS Pattern):
   <div class="executive-container" style="display: flex; flex-direction: column; gap: 2rem;">
     <div class="headline-section" style="background: linear-gradient(135deg, rgba(197,170,106,0.12), rgba(197,170,106,0.06)); border-left: 4px solid var(--olito-gold); padding: 2rem; text-align: center;">
       <h2 style="font-size: 1.8rem; color: white; font-weight: 700;">Main Strategic Insight</h2>
     </div>
     <div class="analysis-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
       <!-- Maximum 2 insight panels -->
     </div>
   </div>

2. DATA INSIGHT LAYOUT (WSFS CRE Gauge Pattern):
   <div class="data-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; align-items: start;">
     <div class="visualization-section" style="background: rgba(255,255,255,0.04); border: 1px solid var(--olito-gold-border); padding: 2rem; text-align: center;">
       <!-- Single purposeful chart/gauge/metric -->
     </div>
     <div class="insights-section" style="display: flex; flex-direction: column; gap: 1rem;">
       <!-- Maximum 3-4 insight panels -->
     </div>
   </div>

3. SIMPLE THREE-COLUMN (Tech Architecture Pattern):
   <div class="strategy-grid" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2rem; align-items: start;">
     <div class="column" style="padding: 1.5rem; height: 100%;">
       <h3 style="font-size: 1.8rem; color: white; font-weight: 700;">Pillar Title</h3>
       <p style="color: var(--olito-gold); font-size: 1.1rem; margin: 0.5rem 0;">Brief subtitle</p>
       <p style="color: #9fb3c8; font-size: 1rem; margin-bottom: 1.5rem;">Single sentence description</p>
       <!-- Maximum 3-4 bullet points -->
     </div>
   </div>

4. STRATEGIC WHITESPACE PRINCIPLES:
   - Padding: 2-3rem minimum for main sections
   - Gaps: 1.5-2rem between major elements  
   - Margins: 1-1.5rem between related items
   - Line-height: 1.4-1.6 for readability
   - Max-width: 80ch for text blocks

5. REFINED TYPOGRAPHY HIERARCHY:
   - Main title: font-size: 2.5rem; font-weight: 700; color: var(--olito-gold);
   - Section headers: font-size: 1.8rem; font-weight: 600; color: white;
   - Panel titles: font-size: 1.1rem; font-weight: 600; color: white;
   - Body text: font-size: 0.95rem; color: #cbd5e1; line-height: 1.4;
   - Subtitles: font-size: 1.05rem; color: #9fb3c8;

6. PURPOSEFUL VISUAL ELEMENTS:
   - Icons: Simple, 24-32px, consistent style, serve categorization
   - Borders: 1px solid with rgba(255,255,255,0.1-0.3) opacity
   - Backgrounds: rgba(255,255,255,0.04-0.08) for subtle panels
   - Accent colors: var(--olito-gold) strategically, not everywhere
            """,
            "fulton-base": """
REFINED PATTERNS FOR FULTON FRAMEWORK:

1. CLEAN METRIC DISPLAY (Avoid Dense Dashboards):
   <div class="focused-metrics" style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; max-width: 600px; margin: 0 auto;">
     <div class="metric-card" style="background: white; border-left: 4px solid var(--fulton-blue); padding: 2rem; text-align: center;">
       <div style="font-size: 3rem; font-weight: 700; color: var(--fulton-blue); line-height: 1;">92%</div>
       <div style="color: #666; font-size: 1rem; margin-top: 0.5rem;">Customer Satisfaction</div>
     </div>
   </div>

2. STRATEGIC COMPARISON LAYOUT:
   <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 3rem;">
     <div style="background: rgba(30,75,114,0.05); border-left: 3px solid var(--fulton-blue); padding: 2rem;">
       <h3 style="color: var(--fulton-blue); font-size: 1.5rem; margin-bottom: 1rem;">Current State</h3>
       <!-- Maximum 3 bullet points -->
     </div>
     <div style="background: rgba(197,170,106,0.05); border-left: 3px solid var(--fulton-gold); padding: 2rem;">
       <h3 style="color: var(--fulton-gold); font-size: 1.5rem; margin-bottom: 1rem;">Future State</h3>
       <!-- Maximum 3 bullet points -->
     </div>
   </div>

3. MINIMAL CONTENT PRINCIPLES:
   - Single key message per slide
   - Maximum 2-3 main sections
   - Generous padding and spacing
   - Strategic use of brand colors
   - Clean typography hierarchy
            """
        }
    
    def _load_visual_components(self) -> dict:
        """Load visual component templates for rich content."""
        return {
            "gauge": """
            <svg class="gauge-svg" viewBox="0 0 240 140" xmlns="http://www.w3.org/2000/svg">
              <path d="M20,120 A100,100 0 0,1 220,120" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="12"/>
              <path d="M20,120 A100,100 0 0,1 {angle_x},{angle_y}" fill="none" stroke="var(--olito-gold)" stroke-width="12"/>
              <text x="120" y="95" text-anchor="middle" font-size="24" fill="var(--olito-gold)" font-weight="bold">{value}%</text>
            </svg>
            """,
            
            "metric_card": """
            <div class="metric-card" style="background: rgba(255,255,255,0.04); border-left: 4px solid var(--olito-gold); padding: 1.5rem;">
              <div style="font-size: 2.5rem; font-weight: 700; color: var(--olito-gold);">{value}</div>
              <div style="font-size: 0.9rem; color: #9fb3c8; margin-top: 0.5rem;">{label}</div>
              <div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 0.5rem;">{context}</div>
            </div>
            """,
            
            "insight_panel": """
            <div class="insight-panel" style="background: rgba(255,255,255,0.04); border: 1px solid var(--olito-gold-border); padding: 1.5rem; border-radius: 8px;">
              <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                <div style="width: 32px; height: 32px; background: var(--olito-gold); border-radius: 50%; display: grid; place-items: center;">
                  <span style="font-weight: bold; color: #0b1a2f;">{icon}</span>
                </div>
                <h3 style="font-size: 1.1rem; color: white; font-weight: 600;">{title}</h3>
              </div>
              <p style="color: #cbd5e1; line-height: 1.5;">{content}</p>
            </div>
            """
        }
    
    def _load_html_templates(self) -> dict:
        """Load complete HTML templates for different patterns."""
        # This would load the actual templates from the WSFS examples
        # For now, returning structure guidance
        return {
            "base_structure": """
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8" />
              <meta name="viewport" content="width=device-width, initial-scale=1.0" />
              <title>{title}</title>
              <link rel="stylesheet" href="../../framework/css/{framework}.css" />
              <style>
                /* Custom styles following McKinsey/BCG standards */
                {custom_styles}
              </style>
            </head>
            <body>
              <div class="of-slide-container">
                <div class="of-slide">
                  {content}
                </div>
              </div>
            </body>
            </html>
            """
        }
    


# Global enhanced slide generator instance
slide_generator = None

def initialize_dspy():
    """Initialize DSPy with the configured OpenAI model for rich slide generation."""
    global slide_generator
    
    try:
        # Format model for DSPy 3.0+ (requires provider/model format)
        model = settings.OPENAI_MODEL
        if "/" not in model:
            model = f"openai/{model}"
        
        # Initialize DSPy LM with model-specific requirements
        # For rich HTML generation, we need higher token limits
        if model.endswith("gpt-5") or "gpt-5" in model:
            # GPT-5 requires temperature=1.0 and large completion window.
            lm = dspy.LM(
                model=model,
                api_key=settings.OPENAI_API_KEY,
                temperature=1.0,
                max_tokens=30000  # Increased for rich HTML output
            )
        else:
            # Standard models optimized for speed
            lm = dspy.LM(
                model=model,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=15000,  # Balanced for speed and quality
                temperature=0.6    # Slightly lower for consistency
            )
        
        dspy.configure(lm=lm)
        
        # Create optimized slide generator instance
        slide_generator = OptimizedSlideGenerator()
        
        logger.info(f"Optimized DSPy slide generator initialized with model: {model}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize DSPy: {e}")
        return False


@router.post("/generate-slide", response_model=SlideGenerationResponse)
async def generate_slide(request: SlideGenerationRequest) -> SlideGenerationResponse:
    """Generate a presentation slide from natural language description.
    
    Optimized for speed: targets < 2 minute generation time.
    """
    
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
        
        # Generate the slide with enhanced pipeline
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
                "detected_type": slide_type,
                "slide_pattern": getattr(result, 'slide_pattern', 'unknown'),
                "primary_message": getattr(result, 'primary_message', 'Not available'),
                "metadata": getattr(result, 'metadata', {})
            }
        )
        
        logger.info(f"Slide generated successfully ({len(result.slide_html)} chars)")
        return response
        
    except Exception as e:
        logger.error(f"Slide generation failed: {e}")
        # Return error in format expected by frontend
        raise HTTPException(
            status_code=500,
            detail=str(e)  # Frontend expects 'detail' field in error response
        )

def detect_slide_type(request: str) -> str:
    """Detect the type of slide from the request using refined patterns."""
    request_lower = request.lower()
    
    if any(word in request_lower for word in ['summary', 'executive', 'overview', 'key takeaways']):
        return 'executive_summary'
    elif any(word in request_lower for word in ['gauge', 'chart', 'visualization', 'data', 'percentage', 'metrics']):
        return 'data_insight'
    elif any(word in request_lower for word in ['compare', 'comparison', 'versus', 'vs', 'traditional vs', 'current vs']):
        return 'strategic_comparison'
    elif any(word in request_lower for word in ['three', '3', 'pillars', 'capabilities', 'approaches', 'columns']):
        return 'simple_three_column'
    elif any(word in request_lower for word in ['title', 'hero', 'announce', 'message']):
        return 'focused_title'
    else:
        return 'single_focus_message'


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
            type="focused_title",
            request="Create a clean title slide with the message 'AI reduces compliance costs by 60%' - focus on the single key insight with minimal supporting elements",
            description="Clean, focused title slide with single powerful message"
        ),
        SlideExample(
            type="executive_summary",
            request="Executive summary: 'WSFS appears strong but has dangerous CRE over-concentration' with 2 insights: surface view (strong metrics) vs deeper analysis (regulatory risk)",
            description="Executive summary following WSFS pattern - headline + two contrasting insights"
        ),
        SlideExample(
            type="data_insight",
            request="Show customer satisfaction at 92% using a gauge visualization, with 3 key insights about what's driving the improvement - keep it focused and elegant",
            description="Data visualization with purposeful chart and focused insights (WSFS CRE pattern)"
        ),
        SlideExample(
            type="strategic_comparison",
            request="Compare traditional risk management vs AI-powered approach in two clean panels - focus on key differences, not exhaustive lists",
            description="Two-panel comparison with clear contrast and minimal content"
        ),
        SlideExample(
            type="simple_three_column",
            request="Show three AI capabilities: predictive analytics, automation, and insights - each column should have title, brief description, and 3 key features maximum",
            description="Clean three-column layout following tech architecture pattern"
        ),
        SlideExample(
            type="single_focus",
            request="Announce 'Q3 revenue up 45% to $5.2M' as the main message with 2-3 supporting metrics - keep it clean and impactful",
            description="Single focused message with minimal supporting elements"
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


# ============================================
# New: OpenAI Responses API slide generation
# ============================================

@router.post("/generate-slide-mini", response_model=SlideGenerationResponse)
async def generate_slide_mini(request: SlideGenerationRequest) -> SlideGenerationResponse:
    """Generate a presentation slide using OpenAI Responses API (gpt-5-mini).
    Leaves the existing DSPy-based endpoint intact, but provides a faster and more
    reliable path mirroring the examination prep workflow approach.
    """
    try:
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not available")

        # Use the examination model setting for parity with examination prep (defaults to gpt-5-mini)
        slide_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL

        # System prompt tuned for professional, minimalist slides (McKinsey-like aesthetics)
        system_prompt = (
            """### **System Prompt**
You are a specialized AI agent that transforms structured text prompts into a single, complete, and visually appealing HTML file for a presentation slide. Your primary function is to act as an expert front-end developer, taking a user's content outline and generating a polished, self-contained `.html` file that is ready to be used.

**Core Directives:**

1.  **Input Format:** You will receive a structured text prompt with a clear hierarchy: a `Slide Title`, a `Part 1` (LHS/Problem), and a `Part 2` (RHS/Solution). Each part will contain a headline and several points, each with a title and descriptive text.
2.  **Output Format:** Your entire output must be a single, valid HTML5 file. All CSS must be embedded within a `<style>` tag in the `<head>`. Do not provide explanations or extraneous text outside of the HTML code itself.
3.  **Templating:** You must use the specific HTML structure and CSS styling demonstrated in the example below. Adhere strictly to the class names (`comparison-container`, `issue-card`, `solution-card`, etc.), color variables, and layout provided. The goal is consistency in design.
4.  **Icon Generation:** When the prompt includes the instruction `(add icon)`, you must select and generate an appropriate and high-quality SVG icon that visually represents the concept described. The SVG code must be embedded directly into the HTML.
      * For the "Problem" side, icons should be styled with a red theme.
      * For the "Solution" side, icons should be styled with a gold/brand theme and often represent success, partnership, or efficiency.
5.  **Content Mapping:**
      * Map the `Slide Title` to the main `<h1>` element.
      * Map `Part 1` content to the left-hand column (`.issue-list`).
      * Map `Part 2` content to the right-hand column (`.solution-list`).
      * Each point in the prompt should become a "card" (`.issue-card` or `.solution-card`).
      * The `Footnote` specified in the prompt must be placed in the designated footnotes container at the bottom of the slide (`.of-footnotes`), not directly under its respective headline.
6.  **Static Assets:** The HTML will reference static assets like logos (e.g., `../../framework/assets/logo2.png`). You must include these `<img>` tags with the correct `src` paths as shown in the example. Assume this file structure is fixed.

-----

### **Exemplar: Perfect Input and Output**

Use this example as your definitive guide for structure, styling, and execution.

**[START OF EXAMPLE]**

**Prompt:**

```
Slide Title: We know 95% of AI pilots fail. Here’s how we don't

Part 1: The Problem (LHS)
Headline: Why most AI pilots fail
(Footnote: Source: MIT 'State of AI in Business 2025' Report)

Context management (add icon)
Text: Generic tools are static. They don't learn from feedback or remember your specific context, forcing your team to start from scratch on every single query.

Chatbots (add icon)
Text: Most AI tools are just generic chatbots. They can't manage the complex, multi-step business processes, creating more manual work for your team.

Building yourself (add icon)
Text: Trying to build a tool internally is 2x more likely to fail. These projects often lack a sharp focus on a specific problem, making it impossible to deliver measurable ROI.

Part 2: The Oliver Solution (RHS)
Headline: How Oliver succeeds
(Each point below is a direct counter to the corresponding problem on the left.)

We handle the context (add icon)
Text: Oliver has persistent memory and is designed to learn continuously from two sources: the ever-changing public regulatory landscape and your company preferences, ensuring it gets smarter and more valuable over time.

Purpose-built for workflows (add icon)
Text: Oliver is a complete workflow application, not a chatbot. Its custom user interface is designed specifically for your multi-step processes and will be refined in partnership with you during our pilot.

A focused partnership for guaranteed ROI (add icon)
Text: We solve one this problem exceptionally well. As your partner, we bring our expert AI application built on a model-agnostic backend and integrate it with your systems to deliver measurable ROI in weeks.
```

**Output:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MIT-95 – We know 95% of AI pilots fail. Here's how we succeed</title>
  <link rel="stylesheet" href="../../framework/css/olito-tech.css" />
  <style>
    /* Header with logos */
    .content-header { position: absolute; top: var(--spacing-md); right: var(--spacing-md); display: inline-flex; align-items: center; gap: var(--spacing-sm); }
    .content-header img { height: 28px; opacity: 0.95; width: auto; display: block; }
    .content-header img.header-brain { height: 24px; }
    .content-header img.header-wordmark { height: 20px; }
    .content-header img.header-fulton { height: 70px !important; }

    .content-main { margin-top: 7vh; padding: 0 var(--spacing-2xl); }
    .slide-title {
      font-size: 2.85rem; font-weight: var(--font-weight-bold); line-height: 1.15;
      color: var(--olito-gold); text-align: left; margin-top: var(--spacing-lg);
      margin-bottom: var(--spacing-sm);
      letter-spacing: 0.2px;
    }
    .slide-subtitle { color: #9fb3c8; font-size: 1.05rem; margin-bottom: var(--spacing-xl); max-width: none; width: 100%; }

    /* Two-column comparison layout */
    .comparison-container {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--spacing-2xl);
      margin-top: var(--spacing-lg);
    }

    .comparison-column {
      display: flex;
      flex-direction: column;
    }

    .column-header {
      font-size: 1.4rem;
      font-weight: var(--font-weight-semibold);
      margin-bottom: var(--spacing-md);
      padding-bottom: var(--spacing-sm);
      border-bottom: 2px solid var(--olito-gold-border);
    }

    .column-header.problem {
      color: #ef4444; /* Red for problems */
    }

    .column-header.solution {
      color: var(--olito-gold); /* Gold for solutions */
    }

    .column-footnote {
      font-size: 0.85rem;
      color: #9ca3af;
      margin-top: var(--spacing-xs);
      font-style: italic;
    }

    /* Issue/Solution items */
    .issue-list, .solution-list {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-xl);
      margin-top: var(--spacing-md);
    }

    .issue-card, .solution-card {
      display: flex;
      align-items: flex-start;
      gap: var(--spacing-md);
      padding-bottom: var(--spacing-lg);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .issue-card:last-child, .solution-card:last-child {
      border-bottom: none;
      padding-bottom: 0;
    }

    .card-icon {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      flex-shrink: 0;
      margin-top: var(--spacing-xs);
    }

    .issue-card .card-icon {
      background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #ef4444;
    }

    .solution-card .card-icon {
      background: linear-gradient(135deg, var(--olito-gold-light), transparent);
      border: 1px solid var(--olito-gold-border);
      color: var(--olito-gold);
    }

    .card-icon svg {
      width: 24px;
      height: 24px;
    }

    .card-content {
      flex: 1;
    }

    .card-title {
      font-size: 1.1rem;
      font-weight: var(--font-weight-semibold);
      color: var(--fulton-white);
      margin-bottom: var(--spacing-sm);
    }

    .card-description {
      font-size: 1rem;
      color: #cbd5e1;
      line-height: 1.5;
    }

    /* Footnotes */
    .of-footnotes {
      position: absolute; left: var(--spacing-lg); right: var(--spacing-lg); bottom: var(--spacing-md);
      margin-top: 0; padding: 0; text-align: left;
      font-size: 0.85rem; color: #9ca3af;
    }

    /* Responsive */
    @media (max-width: 1200px) {
      .comparison-container { gap: var(--spacing-xl); }
    }
    @media (max-width: 900px) {
      .comparison-container { 
        grid-template-columns: 1fr; 
        gap: var(--spacing-lg); 
      }
      .slide-title { font-size: 2.3rem; }
    }
    @media (max-width: 640px) {
      .slide-title { font-size: 2.1rem; }
      .column-header { font-size: 1.2rem; }
      .card-title { font-size: 1rem; }
      .card-description { font-size: 0.95rem; }
    }
  </style>
  <meta name="description" content="Why 95% of AI pilots fail and how Oliver succeeds through focused partnership and purpose-built workflows." />
</head>
<body>
  <div class="of-slide-container">
    <div class="of-slide fulton-content-template">
      <div class="of-decorative-element"></div>

      <div class="content-header">
        <img class="header-brain" src="../../framework/assets/logo2.png" alt="Olito Labs Brain" />
        <img class="header-wordmark" src="../../framework/assets/logo3.png" alt="Olito Labs" />
        <span class="of-brand-separator" style="font-size:1rem">+</span>
        <img class="header-fulton" src="../../framework/assets/fulton-logo.png" alt="Fulton Bank" />
      </div>

      <div class="content-main">
        <h1 class="slide-title">We know 95% of AI pilots fail. Here's how we succeed</h1>
        <div class="slide-subtitle"><h2>Oliver succeeds by building custom workflows for your business instead of chatbots</h2></div>

        <div class="comparison-container">
          <div class="comparison-column">
            <div class="column-header problem">Why most AI pilots fail</div>
            
            <div class="issue-list">
              <div class="issue-card">
                <div class="card-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.611L5 14.5" />
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-title">Context management</div>
                  <div class="card-description">Generic tools don't learn from feedback or remember your specific context, forcing your team to start from scratch on every single query.</div>
                </div>
              </div>

              <div class="issue-card">
                <div class="card-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-title">Chatbots</div>
                  <div class="card-description">Most AI tools are just generic chatbots. They can't manage the complex, multi-step business processes, creating more manual work.</div>
                </div>
              </div>

              <div class="issue-card">
                <div class="card-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-title">Building yourself</div>
                  <div class="card-description">Trying to build a tool internally is 2x more likely to fail. Projects lack focus on a specific problem, making it impossible to deliver ROI.</div>
                </div>
              </div>
            </div>
          </div>

          <div class="comparison-column">
            <div class="column-header solution">How Oliver succeeds</div>
            
            <div class="solution-list">
              <div class="solution-card">
                <div class="card-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-title">We handle the context</div>
                  <div class="card-description">Oliver is designed to learn continuously from two sources: the public regulatory landscape and your company preferences.</div>
                </div>
              </div>

              <div class="solution-card">
                <div class="card-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-title">Purpose-built for workflows</div>
                  <div class="card-description">Oliver is a complete workflow application, not a chatbot. Its custom user interface is designed specifically for your multi-step processes.</div>
                </div>
              </div>

              <div class="solution-card">
                <div class="card-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-title">A focused partnership for guaranteed ROI</div>
                  <div class="card-description">We know how to make AI work. We bring our expert AI application built on a model-agnostic backend and integrate it with your systems.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="of-footnotes source-notes">Source: MIT Sloan Management Review, "State of AI in Business 2025" Report.</div>
      <div class="of-decorative-bottom"></div>
    </div>
  </div>
</body>
</html>
```

**[END OF EXAMPLE]**
            """
        )

        # User instruction: describe the requested slide and chosen framework
        user_prompt = (
            f"Framework: {request.css_framework}.\n"
            f"Create a professional slide for this description: {request.slide_request}\n"
            "Return full HTML for a single slide, suitable for standalone viewing."
        )

        # Build request parameters for Responses API
        request_params = {
            "model": slide_model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt}
                    ],
                },
            ],
            "instructions": system_prompt,
            "max_output_tokens": 6000,
            "store": False,
            "stream": False,
        }

        # gpt-5 specific knobs
        if slide_model.startswith("gpt-5"):
            request_params["reasoning"] = {"effort": "low"}
            request_params["text"] = {"verbosity": "medium"}

        resp = client.responses.create(**request_params)

        # Extract text content
        content = ""
        if getattr(resp, 'output', None):
            for item in resp.output:
                if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                    for c in item.content:
                        if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                            content = c.text
                            break
                if content:
                    break
        if not content and hasattr(resp, 'output_text'):
            content = resp.output_text
        if not content:
            raise HTTPException(status_code=500, detail="No content received from OpenAI")

        # Strip accidental markdown fences if present
        stripped = content.strip()
        if stripped.startswith("```"):
            # Remove the first fence line
            first_newline = stripped.find("\n")
            if first_newline != -1:
                stripped = stripped[first_newline+1:]
            # Remove trailing fence if present
            if stripped.endswith("```"):
                stripped = stripped[:-3].strip()

        # Ensure timestamp exists
        if "timestamp-br" not in stripped:
            import datetime
            ts = datetime.datetime.now().strftime("%b %d, %Y • %H:%M %Z")
            # If no timezone available, drop %Z result if empty
            if ts.endswith(" "):
                ts = ts.strip()
            timestamp_html = f'<div class="timestamp-br">Generated {ts}</div>'
            # Insert before closing body if possible
            if "</body>" in stripped:
                stripped = stripped.replace("</body>", f"  {timestamp_html}\n</body>")
            else:
                stripped = stripped + "\n" + timestamp_html

        response = SlideGenerationResponse(
            slide_html=stripped,
            framework_used=request.css_framework,
            model_used=slide_model,
            generation_metadata={
                "request_length": len(request.slide_request),
                "html_length": len(stripped),
                "framework": request.css_framework,
                "method": "responses_api",
            },
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slide generation (mini) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
