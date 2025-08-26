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
            "You are Oliver, generating a single professional HTML slide. "
            "Follow these rules strictly: "
            "1) Output ONLY valid HTML (no markdown fences, no explanations). "
            "2) Use standard 16:9 layout with generous whitespace and clear hierarchy. "
            "3) Title is left-aligned, declarative, under 12 words. "
            "4) Include a bottom-left source element. "
            "5) Link the provided CSS framework using <link rel=\"stylesheet\" href=\"../../framework/css/{framework}.css\" />. "
            "6) If visual elements are used, keep them purposeful and minimal. "
            "7) No extraneous labels or decorations; everything must have a purpose. "
            "8) Make it a professional slide, not just a list of bullets. Think McKinsey slide or BCG slide "
            "9) Try to be visual where possible and minimize wordiness, but only if the end effect with be professional and dignified. "
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
