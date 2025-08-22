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


# DSPy Components
class SynthesizeSlideMessage(dspy.Signature):
    f"""Critically analyze and synthesize the user's request into one clear, focused slide message.
    
    {get_synthesis_context()}
    
    CONSTRAINTS:
    - Title MUST be ≤ 12 words and read as a single declarative sentence (one line, two max)
    - Content must occupy full width; avoid sidebars, tabs, chips, labels, or tags
    - No section labels like 'Executive summary', 'Why it matters', 'The challenge', 'The value'
    - Use at most 3 supporting bullets or a single focused paragraph
    - Every element must serve the core message; remove decorative or redundant text
    """
    
    user_request = dspy.InputField(desc="User's natural language description of desired slide content")
    
    core_insight = dspy.OutputField(desc="Single, declarative sentence (≤12 words) capturing the key message")
    supporting_points = dspy.OutputField(desc="Up to 3 crisp bullets that directly reinforce the insight")
    visual_approach = dspy.OutputField(desc="Minimal visual strategy: 'headline-only' | 'short-bullets' | 'single-metric' | 'single-figure' (pick one)")
    synthesis_rationale = dspy.OutputField(desc="One sentence on what was distilled and why")

class GenerateSlide(dspy.Signature):
    """Generate a minimal, professional slide HTML from a synthesized message (fast)."""
    
    core_insight = dspy.InputField(desc="Single, clear declarative sentence (≤12 words) for the H1 title")
    supporting_points = dspy.InputField(desc="Up to 3 crisp bullets OR short paragraph (≤60 words)")
    visual_approach = dspy.InputField(desc="One of: headline-only | short-bullets | single-metric | single-figure")
    css_framework = dspy.InputField(desc="CSS framework to use: 'olito-tech' or 'fulton-base'")
    design_principles = dspy.InputField(desc="Minimal slide constraints and HTML requirements")
    
    slide_html = dspy.OutputField(desc="Complete HTML (doctype/head/body) with full-width content, one H1, no labels/tags/chips, minimal CSS usage")


class SlideGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        # Prefer Predict (no rationale) for speed
        self.synthesizer = dspy.Predict(SynthesizeSlideMessage, config={"temperature": 0.2, "max_tokens": 400})
        self.generator = dspy.Predict(GenerateSlide, config={"temperature": 0.2, "max_tokens": 1400})
        self.visual_examples = self._load_visual_examples()
        self.design_principles = self._load_design_principles()
    
    def forward(self, slide_request: str, css_framework: str = "olito-tech"):
        # Stage 1: Critical synthesis - distill to one clear message
        logger.info(f"Synthesizing message from: {slide_request[:100]}...")
        synthesis = self.synthesizer(
            user_request=slide_request
        )
        logger.info(f"Synthesized core insight: {synthesis.core_insight}")
        
        # Stage 2: Generate slide from synthesized message
        enhanced_context = self._enhance_request_with_context(slide_request, css_framework)
        
        title = self._constrain_title(synthesis.core_insight)

        result = self.generator(
            core_insight=title,
            supporting_points=synthesis.supporting_points,
            visual_approach=synthesis.visual_approach,
            css_framework=css_framework,
            design_principles=enhanced_context
        )
        
        html_clean = self._sanitize_html(result.slide_html)
        logger.info(f"Generated slide ({len(html_clean)} chars) for insight: {title[:50]}...")
        
        return dspy.Prediction(
            slide_html=html_clean,
            core_insight=title,
            synthesis_rationale=synthesis.synthesis_rationale,
            supporting_points=synthesis.supporting_points
        )

    # ---------- Helpers ----------
    def _constrain_title(self, text: str) -> str:
        try:
            words = text.strip().split()
            if len(words) <= 12:
                return text.strip().rstrip('.').capitalize()
            limited = " ".join(words[:12]).rstrip('.')
            return limited.capitalize()
        except Exception:
            return text

    def _sanitize_html(self, html: str) -> str:
        """Remove common labels and chips; ensure one H1 and full-width container."""
        try:
            import re
            # Remove common section labels
            forbidden = [r"Executive summary", r"Why it matters", r"The challenge", r"The value", r"Overview", r"Summary"]
            for lab in forbidden:
                html = re.sub(rf"<h[12][^>]*>\s*{lab}[^<]*</h[12]>", "", html, flags=re.IGNORECASE)

            # Ensure single H1: demote additional h1s to h2
            h1s = re.findall(r"<h1[\s\S]*?</h1>", html, flags=re.IGNORECASE)
            if len(h1s) > 1:
                first = True
                def repl(m):
                    nonlocal first
                    if first:
                        first = False
                        return m.group(0)
                    return re.sub(r"<h1", "<h2", re.sub(r"</h1>", "</h2>", m.group(0)), flags=re.IGNORECASE)
                html = re.sub(r"<h1[\s\S]*?</h1>", repl, html, flags=re.IGNORECASE)

            # Remove badges/chips
            html = re.sub(r"<span[^>]*class=\"[^\"]*(badge|chip)[^\"]*\"[^>]*>[\s\S]*?</span>", "", html, flags=re.IGNORECASE)

            # Enforce full-width content by removing sidebars if any (basic heuristic)
            html = html.replace("of-sidebar", "of-content-area")
            return html
        except Exception:
            return html
    
    def _enhance_request_with_context(self, request: str, framework: str) -> str:
        """Add framework-specific context with refined design principles."""
        
        # Determine the best pattern for this request
        recommended_pattern = get_pattern_for_request(request)
        pattern_info = REFINED_PATTERNS.get(recommended_pattern, REFINED_PATTERNS['single_focus_message'])
        
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

REFINED DESIGN PRINCIPLES (Minimal, fast):

🎯 FOCUS & CLARITY:
- ONE clear message per slide
- Title ≤ 12 words, single declarative sentence
- Content spans full width; no sidebars or badges
- No labels like "Executive summary" or "Why it matters"

📐 LAYOUT & SPACING:
- Generous whitespace; avoid many small boxes
- Use a single main column layout
- If bullets, keep ≤ 3 items, short phrases

📝 TYPOGRAPHY HIERARCHY:
- H1 only once; body text concise (≤ 60 words if paragraph)

🎨 VISUALS (OPTIONAL):
- Only add a single visual if it materially helps (metric/figure)

📊 DATA VISUALIZATION:
- Prefer a single large metric or one simple figure

RECOMMENDED PATTERN: {recommended_pattern}
PATTERN STRUCTURE: {pattern_info['structure']}

❌ AVOID:
{chr(10).join([f'- {item}' for item in ANTI_PATTERNS['avoid']])}

✅ INSTEAD DO:
{chr(10).join([f'- {item}' for item in ANTI_PATTERNS['instead_do']])}

HTML REQUIREMENTS:
1. Complete HTML with DOCTYPE, head, and body
2. Link to CSS: ../../framework/css/{framework}.css
3. Comprehensive <style> section following the refined principles above
4. Semantic HTML with proper structure
5. Responsive design with media queries

USER REQUEST: {request}
        """.strip()


    def _load_visual_examples(self) -> dict:
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
    
    def _load_design_principles(self) -> str:
        """Load refined design principles based on high-quality slide analysis."""
        return """
REFINED DESIGN PRINCIPLES (McKinsey/BCG Level):

🎯 FOCUS & MESSAGE CLARITY:
   - ONE clear message per slide - everything else supports it
   - Maximum 2-3 main sections total
   - Avoid competing visual elements or messages
   - Each element must serve the central narrative

📐 STRATEGIC WHITESPACE:
   - Generous padding: 2-3rem minimum for main containers
   - Section gaps: 1.5-2rem between major elements
   - Content breathing room: 1rem between related items
   - Don't fill every pixel - emptiness creates elegance

📝 REFINED TYPOGRAPHY:
   - Main titles: 2.5-3rem, var(--olito-gold), font-weight 700
   - Section headers: 1.8-2rem, white, font-weight 600  
   - Panel titles: 1-1.2rem, white, font-weight 600
   - Body text: 0.95-1rem, #cbd5e1, line-height 1.4-1.6
   - Subtitles: 1.05rem, #9fb3c8, context/explanation
   - Maximum 3 different font sizes per slide

🎨 SOPHISTICATED VISUALS:
   - Subtle panel backgrounds: rgba(255,255,255,0.04-0.08)
   - Minimal borders: 1px solid with 0.1-0.3 opacity
   - Strategic accent colors: var(--olito-gold) for emphasis only
   - Simple icons: 24-32px, consistent style, purposeful
   - No decorative elements - every visual serves the message

📊 PURPOSEFUL DATA VISUALIZATION:
   - Single, clear data story per slide
   - Gauges/charts that communicate specific insights
   - Large, impactful numbers with context
   - Avoid multiple competing visualizations
   - Every chart must answer a business question

📄 CONTENT DENSITY CONTROL:
   - Maximum 3-4 bullet points per section
   - Single sentences or short phrases preferred
   - Each insight panel = icon + title + 1 paragraph max
   - Avoid dense text blocks or complex nested information

📡 LAYOUT SOPHISTICATION:
   - CSS Grid for precise alignment and spacing
   - Consistent visual treatment across similar elements
   - Two-column layouts for comparisons/insights
   - Three-column only when truly necessary
   - Single-column for focused messages

❌ CRITICAL ANTI-PATTERNS TO AVOID:
   - Multiple small boxes (webpage-like layouts)
   - Dense text paragraphs or bullet lists
   - More than 4-5 distinct sections
   - Decorative charts without clear purpose
   - Cramped spacing or small fonts
   - Multiple competing messages
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
        
        # Prepare response with synthesis information
        response = SlideGenerationResponse(
            slide_html=result.slide_html,
            framework_used=request.css_framework,
            model_used=settings.OPENAI_MODEL,
            generation_metadata={
                "request_length": len(request.slide_request),
                "html_length": len(result.slide_html),
                "framework": request.css_framework,
                "detected_type": slide_type,
                "core_insight": getattr(result, 'core_insight', 'Not available'),
                "synthesis_rationale": getattr(result, 'synthesis_rationale', 'Not available'),
                "supporting_points": getattr(result, 'supporting_points', [])
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
