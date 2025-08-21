"""
High-quality slide templates and examples for DSPy to learn from.
These templates demonstrate McKinsey/BCG-level visual sophistication.
"""

SLIDE_TEMPLATES = {
    "title_slide": {
        "description": "Hero slide with strong visual impact",
        "html_pattern": """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link rel="stylesheet" href="../../framework/css/{framework}.css" />
  <style>
    .hero-container {{
      height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      position: relative;
      background: linear-gradient(135deg, rgba(197,170,106,0.05) 0%, transparent 50%);
    }}
    .hero-title {{
      font-size: 4rem;
      font-weight: 800;
      color: var(--olito-gold);
      text-align: center;
      margin-bottom: 1rem;
      line-height: 1.1;
      max-width: 80%;
    }}
    .hero-subtitle {{
      font-size: 1.5rem;
      color: #cbd5e1;
      text-align: center;
      max-width: 60%;
      line-height: 1.4;
    }}
    .visual-accent {{
      position: absolute;
      top: 10%;
      right: 10%;
      width: 200px;
      height: 200px;
      background: radial-gradient(circle, var(--olito-gold) 0%, transparent 70%);
      opacity: 0.1;
      border-radius: 50%;
    }}
  </style>
</head>
<body>
  <div class="of-slide-container">
    <div class="of-slide">
      <div class="visual-accent"></div>
      <div class="hero-container">
        <h1 class="hero-title">{main_title}</h1>
        <p class="hero-subtitle">{subtitle}</p>
      </div>
    </div>
  </div>
</body>
</html>
        """
    },
    
    "three_column_comparison": {
        "description": "Three-column layout for comparing options or stages",
        "html_pattern": """
<div class="comparison-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; margin-top: 2rem;">
  <div class="option-card" style="background: rgba(255,255,255,0.04); border: 2px solid var(--olito-gold); border-radius: 12px; padding: 1.5rem;">
    <div class="option-header" style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
      <div class="option-number" style="width: 40px; height: 40px; background: var(--olito-gold); color: white; border-radius: 50%; display: grid; place-items: center; font-weight: bold;">1</div>
      <h3 style="color: white; font-size: 1.25rem; font-weight: 600;">{option1_title}</h3>
    </div>
    <p style="color: #cbd5e1; line-height: 1.5; margin-bottom: 1rem;">{option1_description}</p>
    <div class="option-metrics" style="padding-top: 1rem; border-top: 1px solid rgba(197,170,106,0.2);">
      <div style="font-size: 2rem; font-weight: 700; color: var(--olito-gold);">{option1_metric}</div>
      <div style="font-size: 0.9rem; color: #9fb3c8; text-transform: uppercase;">{option1_label}</div>
    </div>
  </div>
  <!-- Repeat for options 2 and 3 -->
</div>
        """
    },
    
    "process_flow": {
        "description": "Visual process flow with stages and connectors",
        "html_pattern": """
<div class="process-flow" style="display: flex; justify-content: space-between; align-items: center; margin: 3rem 0;">
  <div class="process-stage" style="flex: 1; display: flex; flex-direction: column; align-items: center; position: relative;">
    <div class="stage-icon" style="width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, rgba(197,170,106,0.2), transparent); border: 2px solid var(--olito-gold); display: grid; place-items: center;">
      <svg style="width: 40px; height: 40px; color: var(--olito-gold);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <!-- Icon SVG path -->
      </svg>
    </div>
    <h4 style="color: white; font-size: 1.1rem; margin-top: 1rem; font-weight: 600;">{stage_name}</h4>
    <p style="color: #9fb3c8; font-size: 0.9rem; text-align: center; margin-top: 0.5rem;">{stage_description}</p>
    <!-- Arrow connector -->
    <div style="position: absolute; right: -50%; top: 40px; width: 100%; height: 2px; background: linear-gradient(90deg, var(--olito-gold) 0%, transparent 100%);"></div>
  </div>
  <!-- Repeat for additional stages -->
</div>
        """
    },
    
    "metrics_dashboard": {
        "description": "Key metrics display with visual emphasis",
        "html_pattern": """
<div class="metrics-dashboard" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; margin: 2rem 0;">
  <div class="metric-card" style="background: linear-gradient(135deg, rgba(197,170,106,0.1), transparent); border-left: 4px solid var(--olito-gold); padding: 1.5rem;">
    <div class="metric-value" style="font-size: 3rem; font-weight: 700; color: var(--olito-gold); line-height: 1;">{metric_value}</div>
    <div class="metric-label" style="font-size: 0.9rem; color: #9fb3c8; text-transform: uppercase; margin-top: 0.5rem;">{metric_label}</div>
    <div class="metric-change" style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem;">
      <span style="color: #10b981;">↑ {change_value}%</span>
      <span style="color: #6b7280; font-size: 0.85rem;">vs last period</span>
    </div>
  </div>
  <!-- Repeat for additional metrics -->
</div>
        """
    },
    
    "problem_solution": {
        "description": "Problem-solution narrative with visual contrast",
        "html_pattern": """
<div class="problem-solution-layout" style="display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; margin: 2rem 0;">
  <!-- Problem Side -->
  <div class="problem-section" style="padding: 2rem; background: linear-gradient(135deg, rgba(239,68,68,0.1), transparent); border-radius: 12px;">
    <div class="section-header" style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;">
      <div style="width: 40px; height: 40px; background: #ef4444; border-radius: 50%; display: grid; place-items: center;">
        <svg style="width: 24px; height: 24px; color: white;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 style="color: white; font-size: 1.5rem; font-weight: 600;">The Problem</h3>
    </div>
    <ul style="list-style: none; padding: 0;">
      <li style="display: flex; gap: 1rem; margin-bottom: 1rem;">
        <span style="color: #ef4444;">•</span>
        <span style="color: #cbd5e1;">{problem_point}</span>
      </li>
    </ul>
  </div>
  
  <!-- Solution Side -->
  <div class="solution-section" style="padding: 2rem; background: linear-gradient(135deg, rgba(16,185,129,0.1), transparent); border-radius: 12px;">
    <div class="section-header" style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;">
      <div style="width: 40px; height: 40px; background: #10b981; border-radius: 50%; display: grid; place-items: center;">
        <svg style="width: 24px; height: 24px; color: white;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h3 style="color: white; font-size: 1.5rem; font-weight: 600;">The Solution</h3>
    </div>
    <ul style="list-style: none; padding: 0;">
      <li style="display: flex; gap: 1rem; margin-bottom: 1rem;">
        <span style="color: #10b981;">✓</span>
        <span style="color: #cbd5e1;">{solution_point}</span>
      </li>
    </ul>
  </div>
</div>
        """
    },
    
    "executive_summary": {
        "description": "Executive summary with key takeaways",
        "html_pattern": """
<div class="executive-summary" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(197,170,106,0.3); border-radius: 12px; padding: 2rem; margin: 2rem 0;">
  <div class="summary-header" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem;">
    <h2 style="color: var(--olito-gold); font-size: 1.75rem; font-weight: 600;">Executive Summary</h2>
    <div style="background: var(--olito-gold); color: var(--bg-dark); padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600;">KEY TAKEAWAYS</div>
  </div>
  
  <div class="key-points" style="display: grid; gap: 1.5rem;">
    <div class="key-point" style="display: grid; grid-template-columns: auto 1fr; gap: 1rem; align-items: start;">
      <div style="width: 32px; height: 32px; background: linear-gradient(135deg, var(--olito-gold), transparent); border-radius: 50%; display: grid; place-items: center; color: white; font-weight: bold;">1</div>
      <div>
        <h4 style="color: white; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">{point_title}</h4>
        <p style="color: #cbd5e1; line-height: 1.5;">{point_description}</p>
      </div>
    </div>
    <!-- Repeat for additional points -->
  </div>
  
  <div class="bottom-line" style="margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid rgba(197,170,106,0.2);">
    <strong style="color: var(--olito-gold);">Bottom Line:</strong>
    <span style="color: white; margin-left: 1rem;">{bottom_line_text}</span>
  </div>
</div>
        """
    },
    
    "matrix_2x2": {
        "description": "2x2 strategic positioning matrix",
        "html_pattern": """
<div class="matrix-container" style="position: relative; width: 100%; max-width: 600px; margin: 2rem auto;">
  <div class="matrix-grid" style="display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 2px; background: rgba(197,170,106,0.3); padding: 2px; border-radius: 12px; aspect-ratio: 1;">
    <div class="quadrant" style="background: rgba(255,255,255,0.04); padding: 1.5rem; display: flex; flex-direction: column; align-items: center; justify-content: center;">
      <h4 style="color: var(--olito-gold); font-weight: 600; margin-bottom: 0.5rem;">{q1_title}</h4>
      <p style="color: #cbd5e1; text-align: center; font-size: 0.9rem;">{q1_description}</p>
    </div>
    <!-- Repeat for other quadrants -->
  </div>
  
  <!-- Axis Labels -->
  <div style="position: absolute; bottom: -2rem; left: 50%; transform: translateX(-50%); color: #9fb3c8; font-weight: 600;">{x_axis_label}</div>
  <div style="position: absolute; left: -2rem; top: 50%; transform: rotate(-90deg) translateX(-50%); transform-origin: left center; color: #9fb3c8; font-weight: 600;">{y_axis_label}</div>
</div>
        """
    }
}

# Visual component library
VISUAL_COMPONENTS = {
    "icon_circle": """<div style="width: {size}px; height: {size}px; background: {color}; border-radius: 50%; display: grid; place-items: center; color: white; font-weight: bold;">{content}</div>""",
    
    "gradient_divider": """<div style="background: linear-gradient(180deg, transparent 20%, {color} 35%, {color} 65%, transparent 80%); width: 2px; height: 80%;"></div>""",
    
    "hover_card": """<div style="background: rgba(255,255,255,0.04); border: 2px solid {border_color}; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: transform 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">""",
    
    "metric_display": """
<div style="text-align: center;">
  <div style="font-size: 3rem; font-weight: 700; color: {primary_color}; line-height: 1;">{value}</div>
  <div style="font-size: 0.9rem; color: #9fb3c8; text-transform: uppercase; margin-top: 0.5rem;">{label}</div>
</div>""",
    
    "progress_bar": """
<div style="width: 100%; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;">
  <div style="width: {percentage}%; height: 8px; background: linear-gradient(90deg, {color1}, {color2});"></div>
</div>""",
    
    "callout_box": """
<div style="background: linear-gradient(135deg, rgba(197,170,106,0.1), transparent); border-left: 4px solid var(--olito-gold); padding: 1.5rem; margin: 2rem 0; border-radius: 0 8px 8px 0;">
  <h4 style="color: var(--olito-gold); margin-bottom: 0.5rem; font-weight: 600;">{title}</h4>
  <p style="color: #cbd5e1; line-height: 1.6;">{content}</p>
</div>"""
}

# Common SVG icons for visual elements
SVG_ICONS = {
    "arrow_right": """<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3" /></svg>""",
    
    "check_circle": """<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>""",
    
    "warning": """<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>""",
    
    "chart": """<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>""",
    
    "users": """<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>""",
    
    "lightbulb": """<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>"""
}
