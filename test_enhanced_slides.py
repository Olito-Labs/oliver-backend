#!/usr/bin/env python3
"""
Test script for the enhanced DSPy slide generation system.
Run this to verify the new multi-stage pipeline is working correctly.
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent))

from app.api.slidegenerator import SlideGenerator, initialize_dspy
from app.config import settings

async def test_slide_generation():
    """Test the enhanced slide generation with different layout types."""
    
    print("🧪 Testing Enhanced DSPy Slide Generation System")
    print("=" * 60)
    
    # Initialize DSPy
    print("\n1. Initializing DSPy...")
    success = initialize_dspy()
    if not success:
        print("❌ Failed to initialize DSPy")
        return
    print("✅ DSPy initialized successfully")
    
    # Create slide generator
    generator = SlideGenerator()
    
    # Test cases for different layout patterns
    test_cases = [
        {
            "name": "Foundation Pillars",
            "request": "Show Fulton Bank's growth foundation with two reinforcing pillars: internal transformation and strategic expansion",
            "expected_layout": "foundation_pillars"
        },
        {
            "name": "Process Flow", 
            "request": "Explain the regulatory supervision cycle showing planning, activities, communication, and documentation stages",
            "expected_layout": "process_flow"
        },
        {
            "name": "Three Column",
            "request": "Introduce Oliver with AI agents, orchestration engine, and custom workflows for regulatory compliance",
            "expected_layout": "three_column"
        },
        {
            "name": "Title Slide",
            "request": "Create a title slide for 'AI-Powered Banking Solutions' with subtitle 'Transforming Financial Services'",
            "expected_layout": "title_only"
        }
    ]
    
    print(f"\n2. Testing {len(test_cases)} different slide patterns...")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n   Test {i}: {test_case['name']}")
        print(f"   Request: {test_case['request'][:60]}...")
        
        try:
            # Generate slide
            result = generator(
                slide_request=test_case['request'],
                css_framework="olito-tech"
            )
            
            # Validate results
            if hasattr(result, 'slide_html') and result.slide_html:
                html_length = len(result.slide_html)
                layout_type = getattr(result, 'layout_type', 'unknown')
                
                print(f"   ✅ Generated: {html_length} chars, Layout: {layout_type}")
                
                # Check if HTML contains expected elements
                html = result.slide_html
                checks = {
                    "DOCTYPE": "<!DOCTYPE html>" in html,
                    "CSS Link": "olito-tech.css" in html,
                    "Slide Container": "of-slide-container" in html,
                    "Content Main": "content-main" in html,
                    "Slide Title": "slide-title" in html,
                    "Decorative Elements": "of-decorative-element" in html
                }
                
                passed_checks = sum(checks.values())
                total_checks = len(checks)
                
                if passed_checks == total_checks:
                    print(f"   ✅ All {total_checks} structure checks passed")
                else:
                    print(f"   ⚠️  {passed_checks}/{total_checks} structure checks passed")
                    for check, passed in checks.items():
                        if not passed:
                            print(f"      ❌ Missing: {check}")
                
                # Save sample output for inspection
                output_file = f"test_output_{i}_{layout_type}.html"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"   📄 Saved to: {output_file}")
                
            else:
                print(f"   ❌ Failed: No HTML generated")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n3. Testing Summary")
    print("   Enhanced pipeline includes:")
    print("   • Layout analysis stage")
    print("   • CSS framework context injection") 
    print("   • Pattern-based prompting")
    print("   • Multi-stage DSPy pipeline")
    print("   • Enhanced metadata tracking")
    
    print(f"\n🎉 Enhanced slide generation testing complete!")
    print("   Check the generated HTML files to see the results.")

if __name__ == "__main__":
    # Set up environment if needed
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set. Set it in your environment or .env file.")
        print("   export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    asyncio.run(test_slide_generation())
