from __future__ import annotations

import json
import uuid
import threading
import queue
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator, Dict, Any

import anyio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings
from app.llm_providers import openai_manager  # must expose get_async_client() or get_client()

router = APIRouter(prefix="/api/simple-assistant", tags=["simple-assistant"])

# --- Simple in-memory conversation threading (swap for DB/redis in prod) ---
LAST_RESPONSE_ID: Dict[str, str] = {}

# --- Models ------------------------------------------------------------------
class SimpleAssistantRequest(BaseModel):
    """Simple request model for the assistant workflow."""
    message: str
    conversation_id: Optional[str] = None
    stream: bool = True

class SimpleAssistantResponse(BaseModel):
    """Simple response model for the assistant workflow."""
    response: str
    conversation_id: str
    timestamp: datetime
    model_used: str
    response_id: Optional[str] = None
    usage: Optional[dict] = None

# --- Helpers -----------------------------------------------------------------
def _sse(payload: dict) -> str:
    # Server-Sent Events line; client parses JSON in .data
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def _base_request_params(
    *,
    model: str,
    instructions: str,
    user_message: str,
    previous_response_id: Optional[str],
    user_id: Optional[str],
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "model": model,
        "input": user_message,          # user turn
        "instructions": instructions,   # system
        "max_output_tokens": 2000,
        "store": True,                  # set False if you don't want retention
        "metadata": {"purpose": "simple-assistant"},
    }
    if user_id is not None:
        params["user"] = str(user_id)

    # Keep model-side context
    if previous_response_id:
        params["previous_response_id"] = previous_response_id

    # Reasoning + verbosity knobs (only for reasoning-capable models)
    # Safe defaults; adjust effort as needed.
    if model.startswith(("gpt-5", "o3", "o4")):
        params["reasoning"] = {
            "effort": "medium",         # minimal | low | medium | high
            "summary": "detailed",      # detailed is supported by gpt-5-2025-08-07
        }
        params["text"] = {"verbosity": "medium"}

    else:
        # Non-reasoning models: temperature for some variety
        params["temperature"] = 0.7

    return params

def _system_prompt() -> str:
    # You can swap this per-route or per-tenant if needed.
    return (
        "You are Oliver, a helpful Kannada translator. "
        "You provide clear, concise, and friendly translations of user input. "
        "You still write in English, but you write English words that spell out "
        "the Kannada translation."
    )

# --- Streaming via ASYNC client (preferred) ----------------------------------
async def _stream_with_async_client(
    aclient,
    request_params: Dict[str, Any],
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    accumulated_text = []
    response_id = None

    try:
        # ✅ create(..., stream=True) — NOT .stream(**params) and NOT passing stream kw there
        stream = await aclient.responses.create(stream=True, **request_params)

        async for event in stream:
            etype = getattr(event, "type", None)

            if etype == "response.created":
                # Keep a fast start signal for the UI
                response_id = event.response.id if hasattr(event, "response") else None
                yield _sse({
                    "type": "start",
                    "conversation_id": conversation_id,
                    "response_id": response_id,
                })

            # --- Reasoning channels (models emit either/both) ---
            elif etype in ("response.reasoning_text.delta", "response.reasoning_summary_text.delta"):
                delta = getattr(event, "delta", "")
                if delta:
                    yield _sse({
                        "type": "reasoning",
                        "channel": "summary" if "summary" in etype else "full",
                        "content": delta,
                        "done": False
                    })

            # --- Final answer tokens ---
            elif etype == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    accumulated_text.append(delta)
                    yield _sse({
                        "type": "content",
                        "content": delta,
                        "done": False
                    })

            elif etype in ("response.error", "response.failed"):
                err = getattr(event, "error", "Unknown error")
                yield _sse({"type": "error", "content": err, "done": True})
                return

        # Store the response_id for conversation threading
        LAST_RESPONSE_ID[conversation_id] = response_id or ""

        # Send completion without trying to get final response (stream object doesn't have this method)
        yield _sse({
            "type": "done",
            "done": True,
            "metadata": {
                "conversation_id": conversation_id,
                "response_id": response_id,
                "model_used": settings.OPENAI_MODEL,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "usage": None  # Usage info not available in this streaming pattern
            }
        })

    except Exception as e:
        yield _sse({"type": "error", "content": f"{e}", "done": True})

# --- Streaming via SYNC client (fallback) ------------------------------------
# Offloads the blocking OpenAI stream to a worker thread and relays events
async def _stream_with_sync_client(
    client,
    request_params: Dict[str, Any],
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    q: "queue.Queue[object]" = queue.Queue(maxsize=256)

    def producer():
        try:
            # ✅ create(..., stream=True)
            stream = client.responses.create(stream=True, **request_params)
            for event in stream:
                q.put(event, block=True)
            # Signal completion without trying to get final response
            q.put(("__final__", None))
        except Exception as ex:
            q.put(("__error__", str(ex)))

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    accumulated_text = []
    response_id = None

    while True:
        item = await anyio.to_thread.run_sync(q.get)

        if isinstance(item, tuple) and item and item[0] == "__final__":
            LAST_RESPONSE_ID[conversation_id] = response_id or ""
            yield _sse({
                "type": "done",
                "done": True,
                "metadata": {
                    "conversation_id": conversation_id,
                    "response_id": response_id,
                    "model_used": settings.OPENAI_MODEL,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "usage": None
                }
            })
            return

        if isinstance(item, tuple) and item and item[0] == "__error__":
            yield _sse({"type": "error", "content": item[1], "done": True})
            return

        event = item
        etype = getattr(event, "type", None)

        if etype == "response.created":
            response_id = event.response.id if hasattr(event, "response") else None
            yield _sse({
                "type": "start",
                "conversation_id": conversation_id,
                "response_id": response_id,
            })

        elif etype in ("response.reasoning_text.delta", "response.reasoning_summary_text.delta"):
            delta = getattr(event, "delta", "")
            if delta:
                yield _sse({
                    "type": "reasoning",
                    "channel": "summary" if "summary" in etype else "full",
                    "content": delta,
                    "done": False
                })

        elif etype == "response.output_text.delta":
            delta = getattr(event, "delta", "")
            if delta:
                accumulated_text.append(delta)
                yield _sse({
                    "type": "content",
                    "content": delta,
                    "done": False
                })

        elif etype == "response.error":
            err = getattr(event, "error", "Unknown error")
            yield _sse({"type": "error", "content": err, "done": True})
            return

# --- API routes ---------------------------------------------------------------
@router.post("/chat")
async def simple_assistant_chat(
    request: SimpleAssistantRequest,
    user=Depends(get_current_user)
):
    """
    Simple assistant chat endpoint — now with:
      • reasoning enabled and streamed first
      • non-blocking async streaming (with sync fallback)
      • conversation threading via previous_response_id
    """
    try:
        # Prefer an async client for non-blocking streaming
        get_async = getattr(openai_manager, "get_async_client", None)
        aclient = get_async() if callable(get_async) else None

        # Fallback to sync client (we'll still avoid blocking the event loop)
        client = aclient or openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not initialized")

        conversation_id = request.conversation_id or str(uuid.uuid4())
        previous_id = LAST_RESPONSE_ID.get(conversation_id)

        system_prompt = _system_prompt()

        params = _base_request_params(
            model=settings.OPENAI_MODEL,
            instructions=system_prompt,
            user_message=request.message,
            previous_response_id=previous_id,
            user_id=(getattr(user, "id", None) or getattr(user, "sub", None)),
        )

        if request.stream:
            # Streaming via async client if available; otherwise via sync fallback
            if aclient:
                generator = _stream_with_async_client(aclient, params, conversation_id)
            else:
                generator = _stream_with_sync_client(client, params, conversation_id)

            return StreamingResponse(
                generator,
                media_type="text/event-stream; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    # Configure CORS globally via CORSMiddleware on the app
                },
            )

        # -------- Non-streaming path --------
        # Note: use async if possible to avoid blocking
        if aclient:
            response = await aclient.responses.create(**params)
        else:
            # Sync fallback on the request/response path is OK since it's short-lived
            response = await anyio.to_thread.run_sync(lambda: client.responses.create(**params))

        text = getattr(response, "output_text", "") or ""
        LAST_RESPONSE_ID[conversation_id] = getattr(response, "id", "")

        usage = getattr(response, "usage", None)
        usage_dict = usage.model_dump() if hasattr(usage, "model_dump") else (usage or None)

        return SimpleAssistantResponse(
            response=text,
            conversation_id=conversation_id,
            timestamp=datetime.now(timezone.utc),
            model_used=settings.OPENAI_MODEL,
            response_id=getattr(response, "id", None),
            usage=usage_dict,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")

@router.get("/status")
async def get_assistant_status():
    try:
        provider_info = openai_manager.get_current_provider_info()
        # Prefer async client for streaming
        get_async = getattr(openai_manager, "get_async_client", None)
        aclient = get_async() if callable(get_async) else None
        client_ok = bool(aclient or openai_manager.get_client())

        return {
            "status": "ready" if client_ok else "unavailable",
            "workflow": "simple-assistant",
            "model": settings.OPENAI_MODEL,
            "provider_info": provider_info,
            "endpoints": {
                "chat": "/api/simple-assistant/chat",
                "status": "/api/simple-assistant/status"
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.post("/test")
async def test_assistant(user=Depends(get_current_user)):
    """Quick test endpoint to verify the assistant is working (non-streaming)."""
    try:
        test_request = SimpleAssistantRequest(
            message="Translate: hello friend, how are you?",
            stream=False
        )
        response = await simple_assistant_chat(test_request, user)
        return {
            "test_status": "success",
            "test_response": response,
            "message": "Simple assistant workflow is working correctly!"
        }
    except Exception as e:
        return {
            "test_status": "failed",
            "error": str(e),
            "message": "Simple assistant workflow encountered an error."
        }
