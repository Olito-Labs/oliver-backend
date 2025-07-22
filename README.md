# Oliver Backend

AI-powered compliance assistant backend using DSPy framework with support for multiple LLM providers.

## Features

- 🤖 **DSPy Integration**: Advanced prompting and optimization framework
- 🔄 **Multiple LLM Providers**: Easy switching between OpenAI, Anthropic, and Google
- 📡 **Streaming Responses**: Real-time chat with Server-Sent Events
- 🎯 **Compliance Focused**: Specialized modules for regulatory analysis
- 🚀 **FastAPI**: High-performance, async API framework
- 🐳 **Docker Ready**: Containerized for easy deployment

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- API keys for your chosen LLM provider

### Environment Setup

1. **Clone and navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables:**
   ```bash
   # Set your LLM provider
   LLM_PROVIDER=openai  # or "anthropic" or "google"
   
   # Add your API keys (only need the one you're using)
   OPENAI_API_KEY=your_openai_key_here
   ANTHROPIC_API_KEY=your_anthropic_key_here
   GOOGLE_API_KEY=your_google_key_here
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

- **POST** `/api/chat/stream` - Streaming chat responses
- **POST** `/api/chat` - Non-streaming chat responses

### Provider Management

- **GET** `/api/provider/info` - Get current LLM provider info
- **POST** `/api/provider/switch` - Switch LLM provider

### Health Check

- **GET** `/api/health` - Health check and system status
- **GET** `/api/` - Root endpoint

## Usage Examples

### Basic Chat Request

```python
import httpx
import json

async def chat_example():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/chat",
            json={
                "messages": [
                    {
                        "id": "1",
                        "content": "What are the key components of a BSA/AML compliance program?",
                        "sender": "user",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                ],
                "analysis_type": "compliance"
            }
        )
        return response.json()
```

### Streaming Chat

```python
import httpx
import json

async def streaming_chat():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/chat/stream",
            json={
                "messages": [
                    {
                        "id": "1", 
                        "content": "Help me create an MRA remediation plan",
                        "sender": "user",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                ],
                "analysis_type": "compliance"
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(data)
```

### Switch LLM Provider

```python
async def switch_provider():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/provider/switch",
            json={
                "provider": "anthropic",
                "api_key": "your_anthropic_key"
            }
        )
        return response.json()
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider to use | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GOOGLE_API_KEY` | Google API key | - |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4` |
| `ANTHROPIC_MODEL` | Anthropic model name | `claude-3-sonnet-20240229` |
| `GOOGLE_MODEL` | Google model name | `gemini-1.5-pro` |
| `MAX_TOKENS` | Maximum tokens per response | `2000` |
| `TEMPERATURE` | Model temperature | `0.7` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:3000` |
| `PORT` | Server port | `8000` |

### Switching Providers

You can switch between LLM providers in three ways:

1. **Environment Variable**: Set `LLM_PROVIDER` to `openai`, `anthropic`, or `google`
2. **API Call**: Use the `/api/provider/switch` endpoint
3. **Runtime**: Call `llm_manager.switch_provider()` in Python code

## Development

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── llm_providers.py     # LLM provider management
│   ├── api/                 # API routes
│   │   ├── chat.py
│   │   └── health.py
│   ├── dspy_modules/        # DSPy components
│   │   ├── signatures.py
│   │   └── modules.py
│   └── models/              # Pydantic models
│       └── api.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### Adding New DSPy Modules

1. **Create a signature in `app/dspy_modules/signatures.py`:**
   ```python
   class YourSignature(dspy.Signature):
       """Description of what this module does."""
       input_field = dspy.InputField(desc="Input description")
       output_field = dspy.OutputField(desc="Output description")
   ```

2. **Create a module in `app/dspy_modules/modules.py`:**
   ```python
   class YourModule(dspy.Module):
       def __init__(self):
           super().__init__()
           self.predictor = dspy.ChainOfThought(YourSignature)
       
       def forward(self, input_data):
           return self.predictor(input_field=input_data)
   ```

3. **Use in API endpoints:**
   ```python
   from app.dspy_modules.modules import YourModule
   module = YourModule()
   result = module(input_data="your input")
   ```

## Deployment

### Production with Docker

```bash
# Build production image
docker build -t oliver-backend .

# Run container
docker run -p 8000:8000 \
  -e LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=your_key \
  oliver-backend
```

### Health Monitoring

The `/api/health` endpoint provides:
- Service status
- Current LLM provider information
- System timestamp
- API version

## Troubleshooting

### Common Issues

1. **LLM Provider Initialization Failed**
   - Check that your API key is correct
   - Verify the provider name is one of: `openai`, `anthropic`, `google`
   - Ensure you have credits/quota in your LLM provider account

2. **CORS Errors**
   - Update `FRONTEND_URL` in environment variables
   - Check that your frontend URL is in the CORS allow list

3. **Streaming Not Working**
   - Ensure your client supports Server-Sent Events
   - Check that proxy/load balancer doesn't buffer responses

4. **Import Errors**
   - Make sure all dependencies are installed: `pip install -r requirements.txt`
   - Check Python version is 3.11+

### Logs

```bash
# View logs with Docker Compose
docker-compose logs -f backend

# View logs with Docker
docker logs -f <container_name>
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License. 