# DSPy Streaming Implementation Guide

## Overview

This document describes the implementation of DSPy streaming functionality in the Oliver backend, providing real-time token streaming and status updates for enhanced user experience.

## Architecture

### Core Components

1. **StreamingOliverAssistant** - Main streaming module using DSPy's `streamify`
2. **OliverStatusMessageProvider** - Custom status message provider for progress updates
3. **Enhanced API Models** - Updated Pydantic models for streaming responses
4. **Updated Chat API** - FastAPI endpoints with proper async streaming
5. **Frontend Integration** - React components handling new streaming types

## Features

### 🚀 Token Streaming
- **Real-time token delivery** as they're generated
- **Multiple field streaming** (response, analysis, findings, rationale)
- **Conversation history support** with DSPy History objects
- **Analysis type routing** (general, compliance, document)

### 📊 Status Updates
- **Progress indicators** during LLM processing
- **Module execution status** with custom messages
- **Visual feedback** with emojis and descriptive text
- **Real-time UI updates** via Server-Sent Events

### 🔄 Stream Types

| Type | Description | Frontend Handling |
|------|-------------|-------------------|
| `content` | Main response content tokens | Accumulated and displayed |
| `reasoning` | DSPy Chain-of-Thought process | Stored in metadata |
| `status` | Progress/status messages | Shown in thinking indicator |
| `artifacts` | Generated artifacts | Displayed in canvas |
| `done` | Completion signal | Stops streaming animation |
| `error` | Error messages | Error state handling |

## Implementation Details

### Backend Components

#### 1. Streaming Module (`app/dspy_modules/streaming.py`)

```python
# Key features:
- StreamingOliverAssistant with dspy.streamify
- OliverStatusMessageProvider for progress updates
- Async generator for real-time streaming
- Support for multiple analysis types
- Artifact detection and suggestion
```

#### 2. API Models (`app/models/api.py`)

```python
# Enhanced StreamChunk model:
class StreamChunk(BaseModel):
    type: Literal["content", "reasoning", "status", "artifacts", "done", "error"]
    content: Union[str, List[Dict[str, Any]]]
    done: bool = False
    metadata: Optional[Dict[str, Any]] = None
    field: Optional[str] = None  # DSPy field name
    error: Optional[str] = None
```

#### 3. Chat API (`app/api/chat.py`)

```python
# Updated streaming endpoint:
@router.post("/chat/stream")
async def chat_streaming(request: ChatRequest):
    async def generate_stream():
        async for chunk in streaming_assistant.stream_response(...):
            yield f"data: {json.dumps(chunk)}\n\n"
```

### Frontend Components

#### 1. Store Updates (`lib/store.ts`)

```typescript
// Enhanced streaming handling:
if (data.type === 'content') {
    // Accumulate main content
} else if (data.type === 'reasoning') {
    // Store reasoning in metadata
} else if (data.type === 'status') {
    // Update current status
}
```

#### 2. UI Components (`components/message-bubble.tsx`)

```typescript
// Enhanced ThinkingIndicator:
const ThinkingIndicator = ({ status }: { status?: string }) => {
    // Shows DSPy status messages or default thinking indicator
}
```

## Usage Examples

### Basic Streaming

```python
async for chunk in streaming_assistant.stream_response(
    query="What are BSA/AML requirements?",
    conversation_history=[],
    analysis_type="compliance"
):
    if chunk["type"] == "content":
        print(f"Content: {chunk['content']}")
    elif chunk["type"] == "status":
        print(f"Status: {chunk['content']}")
```

### Frontend Integration

```typescript
// In React component:
useEffect(() => {
    const eventSource = new EventSource('/api/chat/stream');
    eventSource.onmessage = (event) => {
        const chunk = JSON.parse(event.data);
        handleStreamChunk(chunk);
    };
}, []);
```

## Configuration

### DSPy Stream Listeners

```python
# Configure stream listeners for different fields:
stream_listeners = [
    dspy.streaming.StreamListener(signature_field_name="response"),
    dspy.streaming.StreamListener(signature_field_name="rationale")
]
```

### Status Message Provider

```python
class OliverStatusMessageProvider(dspy.streaming.StatusMessageProvider):
    def lm_start_status_message(self, instance, inputs):
        return "🤖 Analyzing your request..."
    
    def module_start_status_message(self, instance, inputs):
        return "🔍 Running compliance analysis..."
```

## Testing

### Backend Testing

```bash
# Run the streaming test script:
cd oliver-backend
python test_streaming.py
```

### API Testing

```bash
# Test debug endpoint:
curl -X POST http://localhost:8000/api/chat/stream/debug \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"content": "Test streaming", "sender": "user"}],
    "analysis_type": "general"
  }'
```

### Frontend Testing

```bash
# Start the development server:
cd oliver-frontend
npm run dev

# Test streaming in browser console:
fetch('/api/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({messages: [...]})
})
```

## Performance Considerations

### Optimization Strategies

1. **Stream Buffering** - DSPy automatically buffers tokens for field boundaries
2. **Chunk Size** - Optimal token grouping for network efficiency
3. **Connection Management** - Proper SSE connection handling
4. **Memory Usage** - Efficient async generator implementation

### Monitoring

- **Chunk Count** - Track streaming performance
- **Latency** - Measure time to first token
- **Error Rates** - Monitor streaming failures
- **Connection Duration** - SSE connection health

## Security Considerations

1. **Input Validation** - All streaming inputs validated
2. **Rate Limiting** - Prevent streaming abuse
3. **Error Handling** - Graceful failure modes
4. **CORS Configuration** - Proper cross-origin setup

## Troubleshooting

### Common Issues

#### 1. No Streaming Output
```python
# Check LLM provider initialization:
provider_info = llm_manager.get_current_provider_info()
print(f"Provider: {provider_info}")
```

#### 2. Frontend Not Receiving Updates
```javascript
// Verify SSE connection:
eventSource.addEventListener('error', (error) => {
    console.error('SSE Error:', error);
});
```

#### 3. Status Messages Not Showing
```python
# Verify status provider is configured:
stream_predict = dspy.streamify(
    module,
    stream_listeners=[...],
    status_message_provider=OliverStatusMessageProvider()
)
```

### Debug Endpoints

- `POST /api/chat/stream/debug` - Raw streaming output
- `GET /api/provider/info` - LLM provider status
- `GET /api/health` - System health check

## Future Enhancements

### Planned Features

1. **Reasoning Visualization** - Expandable reasoning sections
2. **Stream Analytics** - Performance metrics dashboard
3. **Custom Status Messages** - User-defined progress indicators
4. **Multi-field Display** - Parallel field streaming visualization
5. **Streaming History** - Conversation context streaming

### DSPy Integration

1. **Tool Streaming** - Real-time tool execution updates
2. **ReAct Streaming** - Agent loop progress tracking
3. **Pipeline Streaming** - Multi-module pipeline progress
4. **Optimization Streaming** - Real-time optimization feedback

## Dependencies

### Backend
- `dspy-ai>=2.6.27` - Core DSPy with streaming support
- `fastapi>=0.115.6` - Async streaming endpoints
- `sse-starlette>=2.2.0` - Server-Sent Events

### Frontend
- React with async/await support
- EventSource API for SSE
- TypeScript for type safety

## Conclusion

The DSPy streaming implementation provides a robust, real-time streaming experience for Oliver's compliance assistance. With proper token streaming, status updates, and error handling, users receive immediate feedback during AI processing, significantly improving the user experience.

For questions or issues, refer to the troubleshooting section or create an issue in the repository. 