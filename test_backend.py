#!/usr/bin/env python3
"""
Simple test script to verify the Oliver backend setup.
Run this to test your DSPy integration and LLM provider configuration.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_backend():
    """Test the backend components."""
    print("🚀 Testing Oliver Backend Setup...")
    print("=" * 50)
    
    try:
        # Test 1: Import basic modules
        print("✅ Testing imports...")
        from app.config import settings
        from app.llm_providers import llm_manager
        from app.dspy_modules.modules import assistant
        print(f"   Current LLM Provider: {settings.LLM_PROVIDER}")
        print(f"   Current Model: {settings.current_model}")
        
        # Test 2: Test LLM provider initialization
        print("\n✅ Testing LLM provider initialization...")
        provider_info = llm_manager.get_current_provider_info()
        print(f"   Provider Info: {provider_info}")
        
        # Test 3: Test DSPy assistant
        print("\n✅ Testing DSPy assistant...")
        test_query = "What is compliance in financial services?"
        result = assistant(query=test_query)
        print(f"   Query: {test_query}")
        print(f"   Response Type: {result.get('type')}")
        print(f"   Response Preview: {result.get('response', '')[:100]}...")
        
        # Test 4: Test streaming assistant
        print("\n✅ Testing streaming assistant...")
        from app.dspy_modules.modules import streaming_assistant
        print("   Streaming test (first 3 chunks):")
        chunk_count = 0
        async for chunk in streaming_assistant.stream_response("Hello, can you help me with compliance?"):
            print(f"   Chunk {chunk_count + 1}: {chunk}")
            chunk_count += 1
            if chunk_count >= 3:
                break
        
        print("\n🎉 All tests passed! Backend is ready to use.")
        print("\nNext steps:")
        print("1. Make sure your API key is correctly set in the environment")
        print("2. Start the backend: python -m app.main")
        print("3. Test the API: curl http://localhost:8000/api/health")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you've installed dependencies: pip install -r requirements.txt")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("   Check your configuration and API keys")
        return False
    
    return True

def test_environment():
    """Test environment setup."""
    print("🔧 Checking Environment Setup...")
    print("=" * 50)
    
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check required environment variables
    required_vars = ["LLM_PROVIDER"]
    optional_vars = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]
    
    print("Required variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value}")
        else:
            print(f"   ⚠️  {var}: Not set (using default)")
    
    print("\nAPI Keys:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {'*' * 8}{value[-4:] if len(value) > 4 else '****'}")
        else:
            print(f"   ❌ {var}: Not set")
    
    # Check if at least one API key is set
    api_keys_set = any(os.getenv(var) for var in optional_vars)
    if not api_keys_set:
        print("\n❌ No API keys found! Please set at least one:")
        print("   export OPENAI_API_KEY=your_key_here")
        print("   # or")
        print("   export ANTHROPIC_API_KEY=your_key_here")
        print("   # or") 
        print("   export GOOGLE_API_KEY=your_key_here")
        return False
    
    return True

if __name__ == "__main__":
    # Test environment first
    env_ok = test_environment()
    
    if env_ok:
        # Run async backend tests
        asyncio.run(test_backend())
    else:
        print("\n❌ Environment setup failed. Please fix the issues above and try again.")
        sys.exit(1) 