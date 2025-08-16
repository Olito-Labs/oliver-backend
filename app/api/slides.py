from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
import logging
import os

from app.auth import get_current_user
from app.llm_providers import openai_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slides", tags=["slides"])

class SlideGenerationRequest(BaseModel):
    content: str

class SlideGenerationResponse(BaseModel):
    html: str
    reasoning: str = ""

# Load the CSS content for AI context
def load_olito_tech_css() -> str:
    """Load the olito-tech.css content for AI context."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "olito-tech.css")
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # Fallback CSS content if file not found
        return """
        /* Minimal fallback CSS */
        :root {
          --olito-gold: #c5aa6a;
          --fulton-navy: #0f2a44;
          --panel-dark: #122743;
          --font-family: 'Inter', sans-serif;
        }
        .of-slide-container {
          width: 100%; min-height: 100vh;
          display: flex; align-items: center; justify-content: center;
          background: linear-gradient(135deg, #0b1a2f, #0f2a44);
        }
        .of-slide {
          width: 95%; height: 95vh; max-width: 1400px;
          display: flex; flex-direction: column;
          background: var(--panel-dark);
          border: 1px solid rgba(255, 255, 255, 0.10);
          position: relative;
        }
        """

def get_example_slides() -> str:
    """Get example slide HTML structures for AI reference."""
    return """
    Example 1 - Tech Stack Slide:
    <div class="of-slide-container">
      <div class="of-slide">
        <div class="of-decorative-element"></div>
        <div class="content-header">
          <img class="header-brain" src="/logos/logo2.png" alt="Olito Labs" />
        </div>
        <div class="content-main">
          <h1 class="slide-title">Technical Architecture</h1>
          <div class="subtitle">Modern, scalable infrastructure</div>
          <div class="tech-architecture">
            <!-- Content grid here -->
          </div>
        </div>
        <div class="of-decorative-bottom"></div>
      </div>
    </div>

    Example 2 - Content Slide:
    <div class="of-slide-container">
      <div class="of-slide">
        <div class="of-decorative-element"></div>
        <div class="content-header">
          <img class="header-brain" src="/logos/logo2.png" alt="Olito Labs" />
        </div>
        <div class="content-main">
          <h1 class="slide-title">Understanding AI</h1>
          <div class="slide-subtitle">Key concepts and applications</div>
          <div class="content-grid">
            <!-- Bullet points or cards here -->
          </div>
        </div>
        <div class="of-footnotes">Footer content</div>
        <div class="of-decorative-bottom"></div>
      </div>
    </div>
    """

@router.post("/generate", response_model=SlideGenerationResponse)
async def generate_slide(request: SlideGenerationRequest, user=Depends(get_current_user)):
    """Generate a professional slide using AI based on user content."""
    try:
        logger.info(f"Generating slide for user {user['uid']}")
        
        # Load CSS and examples for AI context
        css_content = load_olito_tech_css()
        example_slides = get_example_slides()
        
        # Create the AI prompt
        prompt = f"""You are a professional presentation designer. Create a beautiful, professional 16:9 slide in HTML format.

REQUIREMENTS:
- Use the provided CSS framework (olito-tech.css) for styling
- Create a clear visual hierarchy with title and body content
- Follow Apple's Human Interface Guidelines: clean, minimal, with visual depth
- Use appropriate CSS classes from the framework
- Include proper semantic HTML structure
- Make it visually appealing and professional
- Ensure 16:9 aspect ratio (landscape orientation)

CSS FRAMEWORK TO USE:
{css_content}

EXAMPLE SLIDE STRUCTURES:
{example_slides}

USER REQUEST:
{request.content}

INSTRUCTIONS:
1. Create a complete HTML document with proper DOCTYPE and head section
2. Link to the CSS: <link rel="stylesheet" href="/css/olito-tech.css" />
3. Use appropriate slide structure from examples
4. Create clear title and organized body content
5. Use proper CSS classes for styling
6. Include the decorative elements for visual appeal
7. Make sure content is well-organized and readable

Generate ONLY the complete HTML code. Do not include any explanations or markdown formatting."""

        # Call OpenAI API
        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=503, detail="AI service unavailable")

        response = client.chat.completions.create(
            model=openai_manager.get_model(),
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional presentation designer who creates beautiful, clean slides following Apple's design principles."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            reasoning_effort="medium",
            verbosity="high",
            temperature=0.7,
            max_tokens=4000
        )

        if not response.choices:
            raise HTTPException(status_code=500, detail="No response from AI service")

        generated_html = response.choices[0].message.content.strip()
        reasoning = getattr(response.choices[0].message, 'reasoning', '') or ""

        # Basic validation - ensure it looks like HTML
        if not generated_html.startswith('<!DOCTYPE html>') and not generated_html.startswith('<html'):
            # Wrap in basic HTML structure if needed
            generated_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Slide</title>
    <link rel="stylesheet" href="/css/olito-tech.css" />
</head>
<body>
    {generated_html}
</body>
</html>"""

        logger.info("Slide generated successfully")
        
        return SlideGenerationResponse(
            html=generated_html,
            reasoning=reasoning
        )

    except Exception as e:
        logger.error(f"Error generating slide: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate slide: {str(e)}")

@router.get("/health")
async def slides_health():
    """Health check for slides service."""
    return {"status": "healthy", "service": "slides"}
