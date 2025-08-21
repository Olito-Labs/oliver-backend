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
2. Link to CSS: /framework/css/{framework}.css  
3. Use ONLY olito-tech.css framework classes
4. 16:9 landscape format with effective horizontal space usage
5. Left-aligned titles using .slide-title class (2.85rem, bold, gold)
6. Include .content-header with dual logos (top-right) using /framework/assets/ paths
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

LOGO ASSETS (use these exact paths):
- Olito Brain: /framework/assets/logo2.png
- Olito Wordmark: /framework/assets/logo3.png  
- Fulton Logo: /framework/assets/fulton-logo.png

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


# Training examples for few-shot learning
def get_training_examples():
    """Get training examples from working slide HTML."""
    
    # Foundation Pillars Pattern (slide-02.html)
    foundation_pillars_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Fulton Bank Growth Foundation</title>
  <link rel="stylesheet" href="/framework/css/olito-tech.css" />
</head>
<body>
  <div class="of-slide-container">
    <div class="of-slide fulton-content-template">
      <div class="of-decorative-element"></div>

      <div class="content-header">
        <img class="header-brain" src="/framework/assets/logo2.png" alt="Olito Labs Brain" />
        <img class="header-wordmark" src="/framework/assets/logo3.png" alt="Olito Labs" />
        <span class="of-brand-separator" style="font-size:1rem">+</span>
        <img class="header-fulton" src="/framework/assets/fulton-logo.png" alt="Fulton Bank" />
      </div>

      <div class="content-main">
        <h1 class="slide-title">Fulton Bank is positioned for unprecedented growth</h1>
        <div class="slide-subtitle"><h2>Two reinforcing pillars set the stage for compounding momentum</h2></div>

        <div class="success-foundation">
          <div class="foundation-pillar">
            <div class="pillar-icon">
              <div class="icon-circle">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3.75 8.25h16.5M6 12h12M8.25 15.75h7.5" />
                  <path d="M4.5 3.75h15a.75.75 0 01.75.75v15a.75.75 0 01-.75.75h-15a.75.75 0 01-.75-.75v-15a.75.75 0 01.75-.75z" />
                </svg>
              </div>
            </div>
            <div class="pillar-text">
              <h3>Internal transformation</h3>
              <p>Modernized operations and disciplined cost control form a resilient core for scalable growth.</p>
            </div>
          </div>
          <div class="foundation-plus">+</div>
          <div class="foundation-pillar">
            <div class="pillar-icon">
              <div class="icon-circle">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 21h18M5 10l7-7 7 7M5 10v11h5v-6h4v6h5V10" />
                </svg>
              </div>
            </div>
            <div class="pillar-text">
              <h3>Strategic expansion</h3>
              <p>Republic First integration expands Greater Philadelphia and unlocks multi‑segment cross‑sell.</p>
            </div>
          </div>
        </div>

        <div class="future-opportunity">
          <h2>
            <span class="highlight">Where can Fulton apply AI to build on this momentum?</span> We suggest the regulatory space.
          </h2>
        </div>
      </div>

      <div class="of-footnotes">Sources: FDIC (Republic First transaction); DBRS/Morningstar; FULT Q2‑2025 earnings.</div>
      <div class="of-decorative-bottom"></div>
    </div>
  </div>
</body>
</html>'''

    # Process Flow Pattern (slide-03.html)  
    process_flow_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Regulatory Supervision Cycle</title>
  <link rel="stylesheet" href="/framework/css/olito-tech.css" />
</head>
<body>
  <div class="of-slide-container">
    <div class="of-slide fulton-content-template">
      <div class="of-decorative-element"></div>

      <div class="content-header">
        <img class="header-brain" src="/framework/assets/logo2.png" alt="Olito Labs Brain" />
        <img class="header-wordmark" src="/framework/assets/logo3.png" alt="Olito Labs" />
        <span class="of-brand-separator" style="font-size:1rem">+</span>
        <img class="header-fulton" src="/framework/assets/fulton-logo.png" alt="Fulton Bank" />
      </div>

      <div class="content-main">
        <h1 class="slide-title">Regulatory scrutiny heightens with growth</h1>
        <div class="slide-subtitle"><h2>Fulton's success will likely attract a brighter supervisory spotlight</h2></div>

        <div class="narrative-flow">
          <div class="mechanism-panel">
            <h3>Current supervisory cycle: A constant demand on resources</h3>
            <div class="cycle-stages-container">
              <div class="stage">
                <div class="stage-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C6.095 4.01 5.25 4.973 5.25 6.108V18.75c0 1.243.87 2.25 1.969 2.25H13.5A2.25 2.25 0 0015.75 18.75v-2.625m3.75-10.5V6.75c0-.621-.504-1.125-1.125-1.125H8.25c-.621 0-1.125.504-1.125 1.125v3.75c0 .621.504 1.125 1.125 1.125h2.25m-2.25-4.5h.008v.008h-.008v-.008z" />
                  </svg>
                </div>
                <p class="stage-name">Planning</p>
                <p class="stage-cost">Senior Management Time</p>
              </div>
              <div class="stage">
                <div class="stage-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                  </svg>
                </div>
                <p class="stage-name">Activities</p>
                <p class="stage-cost">Team Hours & Data Analysis</p>
              </div>
              <div class="stage">
                <div class="stage-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 20.25c4.97 0 9-3.694 9-8.25s-4.03-8.25-9-8.25S3 7.006 3 11.5c0 4.556 4.03 8.25 9 8.25z" />
                  </svg>
                </div>
                <p class="stage-name">Communication</p>
                <p class="stage-cost">Executive Focus</p>
              </div>
              <div class="stage">
                <div class="stage-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                  </svg>
                </div>
                <p class="stage-name">Documentation</p>
                <p class="stage-cost">Compliance Resources</p>
              </div>
            </div>
          </div>

          <div class="problem-hook">
            <h2>The key challenge is no longer just managing risk, but doing so <span class="highlight">without diverting critical focus from growth.</span></h2>
          </div>
        </div>
      </div>

      <div class="of-footnotes">Source: OCC, "Bank Supervision Process," Comptroller's Handbook (June 2018).</div>
      <div class="of-decorative-bottom"></div>
    </div>
  </div>
</body>
</html>'''

    # Three Column Pattern (slide-04.html)
    three_column_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Introducing Oliver</title>
  <link rel="stylesheet" href="/framework/css/olito-tech.css" />
</head>
<body>
  <div class="of-slide-container">
    <div class="of-slide fulton-content-template">
      <div class="of-decorative-element"></div>

      <div class="content-header">
        <img class="header-brain" src="/framework/assets/logo2.png" alt="Olito Labs Brain" />
        <img class="header-wordmark" src="/framework/assets/logo3.png" alt="Olito Labs" />
        <span class="of-brand-separator" style="font-size:1rem">+</span>
        <img class="header-fulton" src="/framework/assets/fulton-logo.png" alt="Fulton Bank" />
      </div>

      <div class="content-main">
        <h1 class="slide-title">Introducing Oliver - your custom regulatory copilot</h1>
        <div class="subtitle"><h2>Oliver has pre-built AI agents that orchestrate into Fulton‑specific workflows</h2></div>

        <div class="section-title">How Oliver Works</div>

        <div class="solution-grid">
          <div class="agents-column">
            <div class="column-header">1. Pre-built AI Agents</div>
            <div class="agents-list">
              <div class="agent-card" style="--agent-color: #1e4b72;">
                <div class="agent-icon">FB</div>
                <div class="agent-content">
                  <div class="agent-title">Fulton Bank Expert</div>
                  <div class="agent-description">Demographics & market analysis, call reports, FDIC data</div>
                </div>
              </div>
              <div class="agent-card" style="--agent-color: #0f2a44;">
                <div class="agent-icon">FD</div>
                <div class="agent-content">
                  <div class="agent-title">FDIC Supervision Expert</div>
                  <div class="agent-description">FILs, examination procedures, RMS manual</div>
                </div>
              </div>
              <div class="agent-card" style="--agent-color: #c5aa6a;">
                <div class="agent-icon">FR</div>
                <div class="agent-content">
                  <div class="agent-title">Federal Reserve Expert</div>
                  <div class="agent-description">SR letters & capital planning, CCAR guidelines</div>
                </div>
              </div>
            </div>
          </div>

          <div class="engine-column">
            <div class="column-header">2. Orchestration</div>
            <div class="engine-stack">
              <div class="connector">→</div>
              <div class="engine-hub">
                <div class="hub-spark spark-1"></div>
                <div class="hub-spark spark-2"></div>
                <div class="hub-spark spark-3"></div>
                <div class="hub-spark spark-4"></div>
              </div>
              <div class="engine-label">Engine</div>
              <div class="connector">→</div>
            </div>
          </div>

          <div class="workflows-column">
            <div class="column-header">3. Custom‑Built Workflows</div>
            <div class="workflows-list">
              <div class="workflow-card">
                <div class="workflow-content">
                  <div class="workflow-title">First Day Letter Automation</div>
                  <div class="workflow-description">Auto‑map requests to data sources; collect and package policies with citations.</div>
                </div>
              </div>
              <div class="workflow-card">
                <div class="workflow-content">
                  <div class="workflow-title">Exam Planning & Scope Alignment</div>
                  <div class="workflow-description">Crosswalk risk assessments to OCC Operating Plan; identify scope focus.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="of-decorative-bottom"></div>
    </div>
  </div>
</body>
</html>'''

    return [
        dspy.Example(
            slide_request="Show Fulton Bank's growth foundation with two reinforcing pillars: internal transformation and strategic expansion",
            slide_html=foundation_pillars_html
        ).with_inputs("slide_request"),
        
        dspy.Example(
            slide_request="Explain the regulatory supervision cycle showing planning, activities, communication, and documentation stages",
            slide_html=process_flow_html
        ).with_inputs("slide_request"),
        
        dspy.Example(
            slide_request="Introduce Oliver with AI agents, orchestration engine, and custom workflows for regulatory compliance",
            slide_html=three_column_html
        ).with_inputs("slide_request")
    ]

# Global slide generator instance
slide_generator = None
optimized_slide_generator = None

def initialize_dspy():
    """Initialize DSPy with the configured OpenAI model and few-shot training."""
    global slide_generator, optimized_slide_generator
    
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
        
        # Create base slide generator
        base_generator = SlideGenerator()
        
        # Get training examples from working slides
        training_examples = get_training_examples()
        
        # Use LabeledFewShot teleprompter for few-shot learning
        teleprompter = dspy.LabeledFewShot(k=len(training_examples))
        
        # Compile the optimized generator with training examples
        logger.info(f"Training slide generator with {len(training_examples)} examples...")
        optimized_slide_generator = teleprompter.compile(
            student=base_generator,
            trainset=training_examples
        )
        
        # Use the optimized generator as the main generator
        slide_generator = optimized_slide_generator
        
        logger.info(f"DSPy initialized successfully with few-shot training. Model: {model}, Examples: {len(training_examples)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize DSPy with few-shot training: {e}")
        # Fallback to base generator if training fails
        try:
            slide_generator = SlideGenerator()
            logger.warning("Falling back to base generator without few-shot training")
            return True
        except Exception as fallback_error:
            logger.error(f"Fallback initialization also failed: {fallback_error}")
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
        is_few_shot_trained = optimized_slide_generator is not None
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
                "pipeline_version": "few_shot_v1" if is_few_shot_trained else "enhanced_v1",
                "few_shot_trained": is_few_shot_trained,
                "training_examples": len(get_training_examples()) if is_few_shot_trained else 0
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
            "few_shot_trained": optimized_slide_generator is not None,
            "training_examples": len(get_training_examples()) if optimized_slide_generator is not None else 0,
            "model": settings.OPENAI_MODEL,
            "frameworks_available": ["olito-tech", "fulton-base"],
            "pipeline_version": "few_shot_v1" if optimized_slide_generator is not None else "enhanced_v1"
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Slide generation health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "dspy_configured": False
        }
