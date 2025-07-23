#!/usr/bin/env python3
"""
Test script for DSPy streaming implementation.
This script tests the new streaming functionality to ensure it works correctly.
"""

import asyncio
import sys
import os

# Add the app directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.llm_providers import llm_manager
from app.dspy_modules.streaming import streaming_assistant

async def test_streaming():
    """Test the DSPy streaming functionality."""
    print("🚀 Testing DSPy Streaming Implementation")
    print("=" * 50)
    
    try:
        # Initialize the LLM provider
        print("📡 Initializing LLM provider...")
        provider_info = llm_manager.get_current_provider_info()
        print(f"✅ Provider: {provider_info['provider']} ({provider_info['model']})")
        
        # Test basic streaming
        print("\n🧪 Testing basic streaming...")
        test_query = "What are the key components of a BSA/AML compliance program?"
        conversation_history = []
        
        chunk_count = 0
        content_chunks = []
        reasoning_chunks = []
        status_messages = []
        
        print(f"📝 Query: {test_query}")
        print("📊 Streaming chunks:")
        print("-" * 30)
        
        async for chunk in streaming_assistant.stream_response(
            query=test_query,
            conversation_history=conversation_history,
            context="",
            analysis_type="compliance"
        ):
            chunk_count += 1
            chunk_type = chunk.get("type", "unknown")
            content = chunk.get("content", "")
            
            if chunk_type == "content":
                content_chunks.append(content)
                print(f"💬 Content: {content[:50]}{'...' if len(content) > 50 else ''}")
            elif chunk_type == "reasoning":
                reasoning_chunks.append(content)
                print(f"🧠 Reasoning: {content[:50]}{'...' if len(content) > 50 else ''}")
            elif chunk_type == "status":
                status_messages.append(content)
                print(f"📊 Status: {content}")
            elif chunk_type == "artifacts":
                print(f"📎 Artifacts: {len(content) if isinstance(content, list) else 'N/A'}")
            elif chunk_type == "done":
                print(f"✅ Done: {chunk.get('metadata', {})}")
            elif chunk_type == "error":
                print(f"❌ Error: {content}")
            
            # Limit output for testing
            if chunk_count > 20:
                print("... (truncated for testing)")
                break
        
        print("-" * 30)
        print(f"📈 Summary:")
        print(f"  Total chunks: {chunk_count}")
        print(f"  Content chunks: {len(content_chunks)}")
        print(f"  Reasoning chunks: {len(reasoning_chunks)}")
        print(f"  Status messages: {len(status_messages)}")
        
        if content_chunks:
            full_content = ''.join(content_chunks)
            print(f"  Full content length: {len(full_content)} characters")
            print(f"  Content preview: {full_content[:100]}...")
        
        if reasoning_chunks:
            full_reasoning = ''.join(reasoning_chunks)
            print(f"  Full reasoning length: {len(full_reasoning)} characters")
            print(f"  Reasoning preview: {full_reasoning[:100]}...")
        
        if status_messages:
            print(f"  Status messages: {status_messages}")
        
        print("\n✅ Streaming test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during streaming test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_different_analysis_types():
    """Test streaming with different analysis types."""
    print("\n🔬 Testing different analysis types...")
    print("=" * 50)
    
    test_cases = [
        ("general", "Tell me about compliance best practices"),
        ("compliance", "Help me create an MRA remediation plan"),
        ("document", "This is a sample policy document that needs review")
    ]
    
    for analysis_type, query in test_cases:
        print(f"\n📋 Testing {analysis_type} analysis...")
        print(f"📝 Query: {query}")
        
        try:
            chunk_count = 0
            async for chunk in streaming_assistant.stream_response(
                query=query,
                conversation_history=[],
                context="",
                analysis_type=analysis_type
            ):
                chunk_count += 1
                if chunk_count <= 3:  # Show first few chunks
                    print(f"  {chunk.get('type', 'unknown')}: {str(chunk.get('content', ''))[:30]}...")
                elif chunk.get('type') == 'done':
                    print(f"  ✅ Completed with {chunk_count} chunks")
                    break
                
                # Safety limit
                if chunk_count > 30:
                    print(f"  ⚠️  Truncated at {chunk_count} chunks")
                    break
                    
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")

def main():
    """Main test function."""
    print("🤖 Oliver Backend - DSPy Streaming Test")
    print("=" * 60)
    
    # Run the async tests
    async def run_all_tests():
        basic_success = await test_streaming()
        await test_different_analysis_types()
        return basic_success
    
    try:
        success = asyncio.run(run_all_tests())
        if success:
            print("\n🎉 All tests passed! DSPy streaming is working correctly.")
            return 0
        else:
            print("\n💥 Some tests failed. Check the output above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 