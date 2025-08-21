"""
Refined slide patterns based on analysis of high-quality WSFS/Tech Architecture slides.
Focus on McKinsey/BCG-level elegance: minimal, focused, sophisticated.

KEY PRINCIPLES EXTRACTED:
1. FOCUS: One clear message per slide, not multiple competing elements
2. MINIMAL COMPLEXITY: Maximum 2-3 main sections, generous whitespace
3. VISUAL HIERARCHY: Clear primary/secondary/tertiary information levels  
4. PURPOSEFUL VISUALS: Charts/gauges that communicate data, not decoration
5. ELEGANT TYPOGRAPHY: Limited font sizes, consistent weights, strategic emphasis
6. SOPHISTICATED COLOR: Subtle backgrounds, strategic accent colors
7. STRATEGIC WHITESPACE: Breathing room, not cramped webpage-style layouts
"""

REFINED_PATTERNS = {
    "executive_summary": {
        "description": "Executive summary with headline + 2-3 key insights (WSFS pattern)",
        "structure": """
        - Large compelling headline (1.8-2.5rem)
        - Subtitle with context (1.05rem, muted)
        - Maximum 2-3 main insight panels
        - Each panel: icon + title + 2-3 bullet points max
        - Strategic whitespace between sections
        - Optional bottom prediction/opportunity section
        """,
        "example_request": "Executive summary showing AI reduces operational risk by 40%, ROI in 6 months, scalable across units"
    },
    
    "data_insight": {
        "description": "Single data visualization + key insights (WSFS CRE gauge pattern)",
        "structure": """
        - Clear title + explanatory subtitle
        - Two-column layout: data viz left, insights right
        - Data viz: gauge, chart, or metric display (not decorative)
        - Insights: 3-4 focused panels with icons
        - Each insight panel: icon + title + single paragraph
        - Source note at bottom
        """,
        "example_request": "Show customer satisfaction at 92% with trend gauge and 3 key insights about improvement drivers"
    },
    
    "strategic_comparison": {
        "description": "Two-panel comparison with clear contrast (Surface vs Deeper pattern)",
        "structure": """
        - Title focusing on the comparison insight
        - Two equal-width panels side by side
        - Each panel: header icon + title + subtitle + 3-4 insights max
        - Visual distinction between panels (colors, borders)
        - Consistent formatting, contrasting content
        - Optional bottom section for implications
        """,
        "example_request": "Compare traditional risk management vs AI-powered approach with key differences"
    },
    
    "simple_three_pillar": {
        "description": "Clean three-column layout with focused content (Tech Architecture pattern)",
        "structure": """
        - Clear title + single-line subtitle
        - Three equal columns with generous spacing
        - Each column: title + subtitle + revenue indicator + description + 3-4 items max
        - Consistent visual treatment across columns
        - Color coding for different types/categories
        - Minimal decorative elements
        """,
        "example_request": "Show three AI capabilities: predictive analytics, automation, insights with key features"
    },
    
    "single_focus_message": {
        "description": "One powerful message with minimal supporting elements",
        "structure": """
        - Large, impactful title (2.5-3rem)
        - Supporting subtitle or context
        - Single central visual element (optional)
        - 2-3 supporting points maximum
        - Generous whitespace throughout
        - Strategic use of accent colors
        """,
        "example_request": "Announce 'AI transformation reduces compliance costs by 60%' with supporting evidence"
    }
}

DESIGN_GUIDELINES = {
    "typography": {
        "title_sizes": ["2.5rem to 3rem for main titles", "1.8rem to 2rem for section headers", "1rem to 1.2rem for panel titles"],
        "hierarchy": "Use font weight (300-700) and color for hierarchy, not just size",
        "limits": "Maximum 3 different font sizes per slide",
        "colors": ["var(--olito-gold) for primary titles", "#9fb3c8 for subtitles", "#cbd5e1 for body text", "white for section headers"]
    },
    
    "layout": {
        "sections": "Maximum 2-3 main sections per slide",
        "whitespace": "Generous padding (2-3rem), space between sections (1.5-2rem)",
        "grid": "Use CSS Grid for precise alignment, avoid flexbox complexity",
        "responsive": "Single column on mobile, maintain hierarchy"
    },
    
    "visual_elements": {
        "purpose": "Every visual element must serve the message, no decoration",
        "icons": "Simple, consistent style - use for categorization/emphasis only",
        "colors": "Subtle backgrounds (rgba 0.04-0.08), strategic accent colors",
        "borders": "Minimal, 1px, subtle opacity (0.1-0.3)",
        "shadows": "Very subtle if any, avoid heavy drop shadows"
    },
    
    "content_density": {
        "bullet_points": "Maximum 3-4 per section",
        "text_length": "Single sentences or short phrases preferred",
        "panels": "Each insight panel = icon + title + 1 paragraph max",
        "focus": "One key message, everything else supports it"
    }
}

ANTI_PATTERNS = {
    "avoid": [
        "Too many small boxes (webpage-like)",
        "Dense text paragraphs",
        "More than 4-5 distinct sections",
        "Competing visual elements",
        "Decorative charts without clear data story",
        "Small font sizes (under 0.9rem)",
        "Cramped spacing",
        "Multiple competing messages",
        "Complex nested layouts",
        "Excessive color variation"
    ],
    
    "instead_do": [
        "2-3 main sections maximum",
        "Generous whitespace between elements",
        "Single clear message per slide",
        "Purposeful data visualizations",
        "Consistent visual hierarchy",
        "Strategic use of accent colors",
        "Clean, minimal layouts",
        "Focus on one key insight"
    ]
}

def get_pattern_for_request(request: str) -> str:
    """Determine the best pattern based on request content."""
    request_lower = request.lower()
    
    if any(word in request_lower for word in ['summary', 'executive', 'overview', 'key takeaways']):
        return 'executive_summary'
    elif any(word in request_lower for word in ['data', 'metrics', 'gauge', 'chart', 'percentage']):
        return 'data_insight'  
    elif any(word in request_lower for word in ['compare', 'versus', 'vs', 'traditional vs', 'surface vs']):
        return 'strategic_comparison'
    elif any(word in request_lower for word in ['three', '3', 'pillars', 'capabilities', 'approaches']):
        return 'simple_three_pillar'
    else:
        return 'single_focus_message'
