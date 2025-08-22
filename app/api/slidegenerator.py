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
from app.refined_slide_patterns import REFINED_PATTERNS, DESIGN_GUIDELINES, ANTI_PATTERNS, get_pattern_for_request
from app.synthesis_prompts import get_synthesis_context

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["slides"])


# DSPy Components - Enhanced for richer output
class AnalyzeSlideRequest(dspy.Signature):
    """Analyze the user's request to understand what type of slide and content they need.
    
    ANALYSIS FRAMEWORK:
    1. IDENTIFY PATTERN: Is this executive summary, data insight, comparison, etc?
    2. EXTRACT KEY ELEMENTS: What are all the important pieces of information?
    3. DETERMINE VISUAL NEEDS: Does this need charts, metrics, gauges, or comparisons?
    4. ASSESS COMPLEXITY: How much detail is actually needed for professional communication?
    
    DON'T over-simplify. Professional slides often need multiple supporting elements.
    """
    
    user_request = dspy.InputField(desc="User's natural language description of desired slide content")
    
    slide_pattern = dspy.OutputField(desc="Pattern type: 'executive_summary' | 'data_insight' | 'strategic_comparison' | 'three_pillar' | 'focused_message'")
    primary_message = dspy.OutputField(desc="Main message (≤15 words) - declarative and insightful")
    key_elements = dspy.OutputField(desc="List of 3-6 important elements to include in the slide")
    visual_requirements = dspy.OutputField(desc="Visual elements needed: 'gauge' | 'metrics' | 'comparison_panels' | 'process_flow' | 'icon_grid' | 'none'")
    content_depth = dspy.OutputField(desc="Content richness: 'minimal' | 'moderate' | 'comprehensive'")

class StructureSlideContent(dspy.Signature):
    """Structure the slide content based on pattern and requirements.
    
    Create professional, McKinsey-level content structure that:
    - Follows the identified pattern (executive summary, data insight, etc.)
    - Includes all key elements with appropriate depth
    - Organizes information hierarchically
    - Balances synthesis with comprehensiveness
    """
    
    primary_message = dspy.InputField(desc="Main declarative message for the slide")
    key_elements = dspy.InputField(desc="List of important elements to include")
    slide_pattern = dspy.InputField(desc="Pattern type to follow")
    content_depth = dspy.InputField(desc="How rich the content should be")
    
    slide_title = dspy.OutputField(desc="Polished title (≤15 words) that captures the insight")
    slide_subtitle = dspy.OutputField(desc="Supporting context or framing (optional)")
    main_sections = dspy.OutputField(desc="List of 2-4 main content sections with titles and content")
    supporting_data = dspy.OutputField(desc="Key metrics, percentages, or data points to highlight")
    visual_elements = dspy.OutputField(desc="Specific visual components to include and their data")

class GenerateRichHTML(dspy.Signature):
    """Generate professional, visually rich HTML following McKinsey/BCG standards.
    
    Create complete HTML that:
    - Uses sophisticated layouts (grids, panels, cards)
    - Includes appropriate visual elements (gauges, metrics, icons)
    - Follows the pattern structure precisely
    - Maintains professional typography and spacing
    - Is typically 250-400 lines of well-structured HTML
    """
    
    slide_title = dspy.InputField(desc="Polished slide title")
    slide_subtitle = dspy.InputField(desc="Supporting context")
    main_sections = dspy.InputField(desc="Structured content sections")
    supporting_data = dspy.InputField(desc="Key metrics and data points")
    visual_elements = dspy.InputField(desc="Visual components to include")
    slide_pattern = dspy.InputField(desc="Pattern to follow for layout")
    css_framework = dspy.InputField(desc="CSS framework: 'olito-tech' or 'fulton-base'")
    pattern_examples = dspy.InputField(desc="HTML examples from similar high-quality slides")
    
    slide_html = dspy.OutputField(desc="Complete, professional HTML (300+ lines) with rich visuals and sophisticated layout")


class EnhancedSlideGenerator(dspy.Module):
    """Multi-stage slide generator that creates rich, professional slides."""
    
    def __init__(self):
        super().__init__()
        # Three-stage pipeline for richer output
        self.analyzer = dspy.ChainOfThought(AnalyzeSlideRequest)  # Use CoT for better analysis
        self.structurer = dspy.Predict(StructureSlideContent)
        self.html_generator = dspy.Predict(GenerateRichHTML)
        
        # Load rich examples and templates
        self.pattern_examples = self._load_pattern_examples()
        self.visual_components = self._load_visual_components()
        self.html_templates = self._load_html_templates()
    
    def forward(self, slide_request: str, css_framework: str = "olito-tech"):
        # Stage 1: Analyze request to understand needs
        logger.info(f"Analyzing request: {slide_request[:100]}...")
        analysis = self.analyzer(
            user_request=slide_request
        )
        logger.info(f"Detected pattern: {analysis.slide_pattern}, depth: {analysis.content_depth}")
        
        # Stage 2: Structure content based on analysis
        logger.info("Structuring slide content...")
        structure = self.structurer(
            primary_message=analysis.primary_message,
            key_elements=analysis.key_elements,
            slide_pattern=analysis.slide_pattern,
            content_depth=analysis.content_depth
        )
        
        # Stage 3: Generate rich HTML
        logger.info("Generating professional HTML...")
        pattern_html = self._get_pattern_examples(analysis.slide_pattern, css_framework)
        
        html_result = self.html_generator(
            slide_title=structure.slide_title,
            slide_subtitle=structure.slide_subtitle,
            main_sections=structure.main_sections,
            supporting_data=structure.supporting_data,
            visual_elements=structure.visual_elements,
            slide_pattern=analysis.slide_pattern,
            css_framework=css_framework,
            pattern_examples=pattern_html
        )
        
        # Post-process HTML
        final_html = self._enhance_html(html_result.slide_html, analysis.visual_requirements)
        logger.info(f"Generated rich slide ({len(final_html)} chars)")
        
        return dspy.Prediction(
            slide_html=final_html,
            slide_pattern=analysis.slide_pattern,
            primary_message=structure.slide_title,
            metadata={
                "pattern": analysis.slide_pattern,
                "depth": analysis.content_depth,
                "sections": len(structure.main_sections.split('||')) if isinstance(structure.main_sections, str) else len(structure.main_sections),
                "visual_requirements": analysis.visual_requirements
            }
        )

    # ---------- Enhanced Helper Methods ----------
    
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
            # Standard models with increased tokens for rich output
            lm = dspy.LM(
                model=model,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=20000,  # Increased from default
                temperature=0.7    # Balanced creativity
            )
        
        dspy.configure(lm=lm)
        
        # Create enhanced slide generator instance
        slide_generator = EnhancedSlideGenerator()
        
        logger.info(f"Enhanced DSPy slide generator initialized with model: {model}")
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate slide: {str(e)}"
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
