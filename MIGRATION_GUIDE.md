# Oliver Backend Migration Guide: DSPy → OpenAI Responses API

## Overview

This migration replaces the DSPy AI framework with OpenAI's Responses API for simpler, more direct integration while maintaining the same frontend interface.

## Key Changes

### ✅ What's New
- **OpenAI Responses API**: Direct integration with `gpt-4o` and other models
- **Conversation State Management**: Proper `previous_response_id` tracking for context
- **Web Search Integration**: Built-in web search tools for research capabilities  
- **Banking Advisor Prompt**: Specialized compliance intake workflow
- **Simplified Architecture**: Removed 300+ lines of DSPy complexity

### ❌ What's Removed
- DSPy framework and all modules (`app/dspy_modules/`)
- Multi-provider support (Anthropic, Google)
- Custom streaming implementations
- Complex signature definitions

## Environment Variables

### Updated Variables (Railway)
```bash
# Required
OPENAI_API_KEY=sk-...                    # Your OpenAI API key
OPENAI_MODEL=gpt-4o                      # Default model (can use gpt-4.1, gpt-4o, etc.)

# Optional  
MAX_TOKENS=2048                          # Max response tokens
TEMPERATURE=1.0                          # Response creativity (0.0-2.0)
FRONTEND_URL=https://oliver-frontend.vercel.app
PORT=8000

# Remove these (no longer needed):
# LLM_PROVIDER=openai
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AI...
```

## Critical Fixes Implemented

### 1. **Conversation State Management** ✅
- **Problem**: Each message was stateless, losing conversation context
- **Solution**: Proper `previous_response_id` tracking in frontend and backend
- **Impact**: True conversation memory, reduced token usage

### 2. **Web Search Tool Selection** ✅  
- **Problem**: Hardcoded tool names causing 400 errors
- **Solution**: Dynamic tool selection based on model type
- **Code**: `web_search` vs `web_search_preview` based on model

### 3. **Banking Advisor Specialization** ✅
- **Problem**: Generic AI assistant
- **Solution**: Specialized compliance intake workflow
- **Features**: Bank research, workflow classification, professional tone

## Testing Your Migration

Run the test script to verify everything works:

```bash
cd oliver-backend
python test_openai_migration.py
```

**Expected Output:**
```
🚀 Starting OpenAI Migration Tests

🔍 Testing OpenAI client initialization...
✅ OpenAI client initialized: {'provider': 'openai', 'model': 'gpt-4o', ...}

🔍 Testing simple OpenAI Responses API call...
✅ Response received: Hello! I'm Oliver, and I'd be happy to help you with your test...
📝 Response ID: resp_abc123...

🔍 Testing conversation state with previous_response_id...
✅ Conversation state response: You asked me about helping with a quick test...
📝 New Response ID: resp_def456...

🔍 Testing streaming response...
📦 Chunk 1: response.created
📦 Chunk 2: response.in_progress
📦 Chunk 3: response.content_part.done
✅ Streaming complete: Banking compliance involves adhering to regulatory requirements...

🔍 Testing web search tool...
🔍 Using web search tool: web_search
✅ Web search response: Based on current BSA/AML regulations for 2024...

🎯 Test Results: 5/5 tests passed
✅ All tests passed! Migration is successful.
```

## Frontend Changes

### Minimal Changes Required ✅
The frontend requires almost no changes because we maintained the same SSE streaming format:

1. **Added `lastResponseId` tracking** in Zustand store
2. **Updated `sendMessage`** to include `previous_response_id`  
3. **Added `response_id` to metadata** interface
4. **Changed default analysis_type** to `"compliance"`

### Conversation State Flow
```
1. User sends message
2. Frontend includes `previous_response_id: lastResponseId` 
3. Backend passes to OpenAI Responses API
4. OpenAI maintains conversation context automatically
5. Frontend stores new `response_id` for next message
```

## Architecture Benefits

### Before (DSPy)
```
User → Frontend → Next.js API → FastAPI → DSPy → LiteLLM → OpenAI
```

### After (Direct OpenAI)
```  
User → Frontend → Next.js API → FastAPI → OpenAI Responses API
```

### Performance Improvements
- **🚀 Faster Response**: Removed middleware overhead
- **💰 Lower Cost**: Better token usage with conversation state
- **🔧 Easier Debug**: Direct error messages from OpenAI
- **📈 Better Scaling**: Native OpenAI rate limiting and caching

## Deployment Steps

### 1. Backend (Railway)
```bash
# Update environment variables in Railway dashboard
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Remove old variables:
# LLM_PROVIDER, ANTHROPIC_API_KEY, GOOGLE_API_KEY
```

### 2. Frontend (Vercel)
No changes needed - same environment variables work.

### 3. Testing
```bash
# Backend testing
cd oliver-backend  
python test_openai_migration.py

# Frontend testing
cd oliver-frontend
npm run dev
# Test conversation flow manually
```

## Rollback Plan

If needed, rollback is simple:
1. Restore `app/dspy_modules/` from git
2. Revert `requirements.txt` 
3. Restore multi-provider environment variables
4. Redeploy previous version

## Banking Advisor Features

The new system specializes in compliance intake with:

### Workflow Categories
- Marketing-Material Compliance Review
- Examination Preparation  
- MRA / Enforcement Action Remediation
- Change-Management Governance
- New Law / New Regulation Impact Analysis
- Third-Party (FinTech) Risk Assessment

### Research Capabilities
- Automatic bank demographics lookup
- Regulatory charter verification
- Asset size and tier classification
- Primary regulator identification

### Professional Output
- C-suite appropriate language
- Evidence-based analysis
- Inline citations for data sources
- Structured intake process

## Support

For issues:
1. Check Railway logs: `railway logs`
2. Run test script: `python test_openai_migration.py`
3. Verify API key has sufficient credits
4. Check model availability (`gpt-4o` vs `gpt-4.1`)

## Next Steps

After successful migration:
- [ ] Monitor token usage and costs
- [ ] Fine-tune banking advisor prompts
- [ ] Add artifact generation for compliance reports
- [ ] Consider adding document upload capabilities
- [ ] Implement conversation export features 