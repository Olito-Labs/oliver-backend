#!/usr/bin/env python3
"""
Test script for OpenAI Responses API migration.
Verifies that the migration from DSPy to OpenAI is working correctly.
"""

import asyncio
import json
from app.llm_providers import openai_manager
from app.config import settings

def get_test_params(**kwargs):
    """Get test parameters compatible with the current model."""
    base_params = {
        "max_output_tokens": kwargs.get("max_output_tokens", 100),
        "stream": kwargs.get("stream", False),
        "store": kwargs.get("store", True)
    }
    
    # Add model-specific parameters
    if settings.OPENAI_MODEL.startswith("o3"):
        # o3 models don't support temperature
        if "reasoning" not in kwargs:
            base_params["reasoning"] = {"effort": "low", "summary": "brief"}
    else:
        # Other models support temperature
        base_params["temperature"] = kwargs.get("temperature", 0.7)
        if "reasoning" not in kwargs:
            base_params["reasoning"] = {}
    
    # Override with any explicitly provided kwargs
    base_params.update(kwargs)
    return base_params

async def test_openai_client():
    """Test basic OpenAI client initialization."""
    print("🔍 Testing OpenAI client initialization...")
    
    client = openai_manager.get_client()
    if not client:
        print("❌ OpenAI client not initialized")
        return False
    
    provider_info = openai_manager.get_current_provider_info()
    print(f"✅ OpenAI client initialized: {provider_info}")
    return True

async def test_simple_response():
    """Test a simple OpenAI Responses API call."""
    print("\n🔍 Testing simple OpenAI Responses API call...")
    
    try:
        client = openai_manager.get_client()
        
        test_params = get_test_params(max_output_tokens=100, stream=False)
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[{
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello, can you help me with a quick test?"}]
            }],
            instructions="You are Oliver, a helpful AI assistant. Respond briefly and professionally.",
            **test_params
        )
        
        if response.output and len(response.output) > 0:
            content = response.output[0].content[0].text
            print(f"✅ Response received: {content[:100]}...")
            print(f"📝 Response ID: {response.id}")
            return response.id
        else:
            print("❌ No response content received")
            return None
            
    except Exception as e:
        print(f"❌ Error in simple response test: {e}")
        return None

async def test_conversation_state(first_response_id):
    """Test conversation state with previous_response_id."""
    print("\n🔍 Testing conversation state with previous_response_id...")
    
    if not first_response_id:
        print("❌ No first response ID to test conversation state")
        return False
    
    try:
        client = openai_manager.get_client()
        
        test_params = get_test_params(max_output_tokens=100, stream=False)
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[{
                "role": "user", 
                "content": [{"type": "input_text", "text": "What did I just ask you about?"}]
            }],
            instructions="You are Oliver, a helpful AI assistant. Refer to the previous conversation context.",
            previous_response_id=first_response_id,  # Critical: Use conversation state
            **test_params
        )
        
        if response.output and len(response.output) > 0:
            content = response.output[0].content[0].text
            print(f"✅ Conversation state response: {content[:100]}...")
            print(f"📝 New Response ID: {response.id}")
            return True
        else:
            print("❌ No conversation state response received")
            return False
            
    except Exception as e:
        print(f"❌ Error in conversation state test: {e}")
        return False

async def test_streaming():
    """Test streaming response."""
    print("\n🔍 Testing streaming response...")
    
    try:
        client = openai_manager.get_client()
        
        test_params = get_test_params(max_output_tokens=100, stream=True)
        stream = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[{
                "role": "user",
                "content": [{"type": "input_text", "text": "Tell me about banking compliance in one sentence."}]
            }],
            instructions="You are Oliver, a banking compliance expert. Be concise.",
            **test_params
        )
        
        chunks_received = 0
        accumulated_text = ""
        
        for chunk in stream:
            chunks_received += 1
            print(f"📦 Chunk {chunks_received}: {chunk.type}")
            
            if chunk.type == "response.content_part.done":
                if hasattr(chunk, 'part') and hasattr(chunk.part, 'text'):
                    accumulated_text += chunk.part.text
                    
            elif chunk.type == "response.completed":
                print(f"✅ Streaming complete: {accumulated_text[:100]}...")
                return True
                
            elif chunk.type == "response.failed":
                print(f"❌ Streaming failed: {chunk.response.error}")
                return False
        
        return chunks_received > 0
        
    except Exception as e:
        print(f"❌ Error in streaming test: {e}")
        return False

async def test_web_search_tool():
    """Test web search tool integration."""
    print("\n🔍 Testing web search tool...")
    
    try:
        client = openai_manager.get_client()
        web_search_tool_name = openai_manager.get_web_search_tool_name()
        print(f"🔍 Using web search tool: {web_search_tool_name}")
        
        test_params = get_test_params(max_output_tokens=200, stream=False)
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[{
                "role": "user",
                "content": [{"type": "input_text", "text": "What are the latest BSA/AML regulations for 2024?"}]
            }],
            instructions="You are Oliver, a banking compliance expert. Research and provide current information.",
            tools=[{
                "type": web_search_tool_name,
                "user_location": {"type": "approximate", "country": "US"},
                "search_context_size": "medium"
            }],
            **test_params
        )
        
        if response.output and len(response.output) > 0:
            content = response.output[0].content[0].text
            print(f"✅ Web search response: {content[:100]}...")
            return True
        else:
            print("❌ No web search response received")
            return False
            
    except Exception as e:
        print(f"❌ Error in web search test: {e}")
        return False

async def main():
    """Run all migration tests."""
    print("🚀 Starting OpenAI Migration Tests\n")
    print(f"📋 Configuration:")
    print(f"   Model: {settings.OPENAI_MODEL}")
    print(f"   Max Tokens: {settings.MAX_TOKENS}")
    print(f"   Temperature: {settings.TEMPERATURE}")
    print(f"   API Key: {'✅ Set' if settings.OPENAI_API_KEY else '❌ Missing'}\n")
    
    tests_passed = 0
    total_tests = 5
    
    # Test 1: Client initialization
    if await test_openai_client():
        tests_passed += 1
    
    # Test 2: Simple response
    first_response_id = await test_simple_response()
    if first_response_id:
        tests_passed += 1
    
    # Test 3: Conversation state
    if await test_conversation_state(first_response_id):
        tests_passed += 1
    
    # Test 4: Streaming
    if await test_streaming():
        tests_passed += 1
    
    # Test 5: Web search tools
    if await test_web_search_tool():
        tests_passed += 1
    
    print(f"\n🎯 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! Migration is successful.")
        return True
    else:
        print("❌ Some tests failed. Check configuration and API key.")
        return False

if __name__ == "__main__":
    asyncio.run(main()) 