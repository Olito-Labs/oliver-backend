# Oliver Backend

> **Status: archived, not maintained.** Oliver was an early Olito Labs prototype of an AI
> assistant for bank regulatory compliance (examination prep, MRA findings, regulatory
> snapshots). We stopped work on it in late 2025, and it is not part of Olito's current
> product. The code stays public for anyone who wants to read it or run it, but we do not
> accept issues or pull requests, and we do not run a hosted version.
>
> **To run it locally you need your own Supabase project.** The app creates a Supabase
> client at startup, so it does not start without `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
> It reads and writes the tables `studies`, `exam_documents`, `exam_requests`,
> `exam_request_documents` and `user_preferences`, and the storage bucket `exam-documents`.
> The table schema lived in the separate frontend and is not published here, so you must
> create the tables yourself from the fields the code writes in `app/api/`.
> `.env.example` lists every variable.
>
> **Security note:** `app/auth.py` accepts requests without a token as a demo user, and
> `app/main.py` allows any `*.vercel.app` origin through CORS. Both are prototype settings.
> Do not deploy this code with real API keys on a public URL.

AI-powered banking compliance assistant backend using OpenAI Responses API.

## o3 Model Considerations

When using the o3 model, note the following important differences:

### ❌ **Unsupported Parameters**
- `temperature` - Not supported (use reasoning effort instead)
- `top_p` - Not supported (sampling parameters don't apply)
- Other sampling parameters - Not compatible with reasoning models

### ✅ **o3-Specific Features**
- `reasoning.effort`: `"low"`, `"medium"`, `"high"` - Controls reasoning depth
- `reasoning.summary`: `"detailed"` - Provides reasoning explanations
- Enhanced chain-of-thought capabilities

### ⚠️ **Known Limitations**
- **Reasoning summaries may be empty**: In ~90% of API responses, the reasoning summary field may be empty despite requesting `"summary": "detailed"`. This is a known OpenAI API issue.
- **Different cost structure**: o3 uses reasoning tokens in addition to input/output tokens

### 🔧 **Automatic Parameter Handling**
The backend automatically adjusts API parameters based on the model:
```python
# For o3 models: Uses reasoning.effort instead of temperature
# For other models: Uses standard temperature parameter
```

## Features

- 🤖 **OpenAI Integration**: Powered by OpenAI's latest models with function calling
- 📡 **Real-time Streaming**: Token-level streaming with Server-Sent Events
- 🧠 **Reasoning Visualization**: Live Chain-of-Thought process display
- 🔍 **Web Search Integration**: Current information retrieval via web search tools
- 🏦 **Banking Focus**: Specialized prompts for regulatory compliance and risk management
- 💬 **Conversation State**: Maintains context across multi-turn conversations
- 🚀 **FastAPI**: High-performance, async API framework
- 🐳 **Docker Ready**: Containerized for easy deployment

## Architecture

This backend uses OpenAI's Responses API for:
- **Streaming responses** with real-time token delivery
- **Function calling** for web search and tool usage
- **Conversation continuity** via `previous_response_id` parameter
- **Banking-focused system prompts** for compliance assistance

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- OpenAI API key

### Environment Setup

1. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure environment variables:**
   ```bash
   # Required
   OPENAI_API_KEY=your_openai_key_here
   
   # Optional (defaults shown)
   OPENAI_MODEL=o3
   MAX_TOKENS=2048
   TEMPERATURE=0.7
   FRONTEND_URL=http://localhost:3000
   PORT=8000
   ```

### Running with Docker (Recommended)

```bash
# Build and run
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### Running with Python

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

### Chat Endpoints

- **POST** `/api/chat/stream` - Streaming chat with real-time tokens
- **POST** `/api/chat` - Non-streaming chat responses

### System Endpoints

- **GET** `/api/provider/info` - Get OpenAI provider information
- **GET** `/api/health` - Health check and system status
- **GET** `/api/` - Root endpoint

## Usage Examples

### Streaming Chat Request

```bash
curl -X POST "http://localhost:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "id": "1",
        "content": "What are the key BSA/AML requirements for community banks?",
        "sender": "user",
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ],
    "analysis_type": "compliance",
    "stream": true
  }'
```

### Non-streaming Chat Request

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "id": "1", 
        "content": "Help me understand CECL implementation requirements",
        "sender": "user",
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ],
    "analysis_type": "compliance"
  }'
```

## Streaming Response Format

The streaming endpoint returns Server-Sent Events with the following event types:

```typescript
// Content tokens (main response)
{ "type": "content", "content": "token", "done": false }

// Reasoning/thinking process  
{ "type": "reasoning", "content": "💭 Searching for current regulations...", "done": false }

// Status updates
{ "type": "status", "content": "🔍 Executing web search...", "done": false }

// Completion with metadata
{ "type": "done", "content": "", "done": true, "metadata": {...} }
```

## Banking Compliance Focus

Oliver is specialized for banking institutions and provides:

- **Institution validation** (charter type, asset size, regulators)
- **Workflow classification** (MRA remediation, exam prep, compliance reviews)
- **Current regulatory research** via web search integration
- **Evidence-based responses** with source citations

Supported analysis types:
- `general` - General banking compliance questions
- `compliance` - Specific regulatory compliance analysis  
- `document` - Document review and analysis

## Development

### Testing

```bash
# Test OpenAI integration
python test_openai_migration.py

# Check system health
curl http://localhost:8000/api/health
```

### Project Structure

```
oliver-backend/
├── app/
│   ├── api/
│   │   ├── chat.py          # Main chat endpoints
│   │   └── health.py        # Health checks
│   ├── models/
│   │   └── api.py           # Pydantic models
│   ├── config.py            # Configuration
│   ├── llm_providers.py     # OpenAI client management
│   └── main.py              # FastAPI application
├── requirements.txt         # Dependencies
├── Dockerfile              # Container configuration
├── docker-compose.yml     # Development setup
└── test_openai_migration.py # Integration tests
```

## Deployment

### Railway Deployment

This backend is configured for Railway deployment:

1. **Set environment variables** in Railway dashboard:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (optional, defaults to o3)
   - `FRONTEND_URL` (your frontend domain)

2. **Deploy** from this repository - Railway will automatically use the Dockerfile

### Health Monitoring

The `/api/health` endpoint provides:
- OpenAI client connectivity status
- Provider configuration details
- System timestamp and version

## License

MIT License - see LICENSE file for details.# Clean competitive intelligence implementation
# Dummy change - Mon Sep  8 18:19:58 EDT 2025
