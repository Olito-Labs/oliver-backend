from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator
import json
import asyncio
from datetime import datetime

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings

router = APIRouter(prefix="/api/regulatory-snapshot", tags=["regulatory-snapshot"])


async def send_reasoning_step(step: Dict[str, Any]) -> str:
    """Format a reasoning step as SSE data"""
    return f"data: {json.dumps({'type': 'reasoning_step', 'data': step})}\n\n"


async def send_regulatory_snapshot_chunk(content: str) -> str:
    """Format a regulatory snapshot text chunk as SSE data"""
    return f"data: {json.dumps({'type': 'regulatory_snapshot_chunk', 'data': {'content': content}})}\n\n"


async def send_completion(data: Dict[str, Any]) -> str:
    """Format completion data as SSE data"""
    return f"data: {json.dumps({'type': 'completion', 'data': data})}\n\n"


async def send_error(error_message: str) -> str:
    """Format error as SSE data"""
    return f"data: {json.dumps({'type': 'error', 'data': {'message': error_message}})}\n\n"


class ReasoningStep:
    def __init__(self, title: str, content: str, icon: str = "brain", details: str = None):
        self.id = str(uuid.uuid4())
        self.title = title
        self.content = content
        self.status = "active"
        self.timestamp = datetime.utcnow().isoformat()
        self.icon = icon
        self.details = details

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "timestamp": self.timestamp,
            "icon": self.icon,
            "details": self.details
        }

    def complete(self):
        self.status = "completed"
        return self

    def error(self, error_message: str):
        self.status = "error"
        self.content = error_message
        return self


@router.post("/generate")
async def stream_regulatory_snapshot(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Stream generation of a regulatory snapshot summary for an institution using GPT-5-mini.

    This endpoint generates a 3-sentence regulatory snapshot when a user enters their institution name.
    Uses the same streaming pattern as exam prep workflow.
    """
    import uuid

    institution_name = (payload.get("institution_name") or "").strip()

    if not institution_name:
        # Default fallback when no institution name is provided
        institution_name = "the banking industry"

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection confirmation
            yield "data: {\"type\": \"connected\"}\n\n"

            # Step 1: Initialize AI Model
            step1 = ReasoningStep(
                "Initializing Regulatory Analysis Engine",
                f"Preparing to analyze regulatory landscape for {institution_name}...",
                "brain"
            )
            yield await send_reasoning_step(step1.to_dict())
            await asyncio.sleep(0.5)

            client = openai_manager.get_client()
            if not client:
                step1.error("OpenAI client not available")
                yield await send_reasoning_step(step1.to_dict())
                yield await send_error("AI analysis service unavailable")
                return

            step1.complete()
            step1.content = f"Model {settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL} connected successfully."
            yield await send_reasoning_step(step1.to_dict())

            # Step 2: Generate Regulatory Snapshot
            step2 = ReasoningStep(
                "Generating Regulatory Snapshot",
                f"Creating a comprehensive 3-sentence regulatory summary for {institution_name}...",
                "lightbulb"
            )
            yield await send_reasoning_step(step2.to_dict())
            await asyncio.sleep(0.5)

            # Use examination model (defaults to GPT-5-mini)
            exam_model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL

            system_prompt = (
                "You are Oliver, a regulatory compliance expert. Generate a succinct 3-sentence "
                "regulatory snapshot summary for a financial institution. Focus on current regulatory "
                "trends, key risks, and compliance priorities that would be relevant to bank examiners "
                "and risk management professionals. Keep it professional, actionable, and specific to "
                "the institution mentioned. Return only the 3-sentence summary, nothing else."
            )

            user_prompt = (
                f"Generate a 3-sentence regulatory snapshot summary for {institution_name}. "
                "Focus on current regulatory landscape, key compliance priorities, and emerging risks."
            )

            # Stream the regulatory snapshot generation using GPT-5-mini
            full_text = ""
            try:
                stream_params = {
                    "model": exam_model,
                    "input": [{
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    }],
                    "instructions": system_prompt,
                    "max_output_tokens": 500,  # Concise 3-sentence response
                    "store": False,
                    "stream": True,
                }

                # Configure GPT-5 specific parameters
                if exam_model.startswith("gpt-5"):
                    stream_params["reasoning"] = {"effort": "low"}  # Quick analysis
                    stream_params["text"] = {"verbosity": "medium"}

                # Use streaming context manager for real-time output
                with client.responses.stream(**stream_params) as resp_stream:
                    for event in resp_stream:
                        ev_type = getattr(event, 'type', '')

                        if ev_type == 'response.output_text.delta':
                            delta = getattr(event, 'delta', None)
                            if delta:
                                full_text += delta
                                yield await send_regulatory_snapshot_chunk(delta)
                                await asyncio.sleep(0.05)  # Small delay for smooth streaming

                        elif ev_type == 'response.error':
                            err = getattr(event, 'error', None)
                            msg = str(err) if err else 'Unknown error'
                            step2.error(f"OpenAI streaming error: {msg}")
                            yield await send_reasoning_step(step2.to_dict())
                            yield await send_error(f"Regulatory snapshot generation failed: {msg}")
                            return

                        elif ev_type == 'response.completed':
                            # Stream completed successfully
                            break

            except Exception as stream_ex:
                # Fallback to non-streaming if stream fails
                try:
                    fallback_params = {
                        "model": exam_model,
                        "input": [{
                            "role": "user",
                            "content": [{"type": "input_text", "text": user_prompt}],
                        }],
                        "instructions": system_prompt,
                        "max_output_tokens": 500,
                        "store": False,
                        "stream": False,
                    }

                    if exam_model.startswith("gpt-5"):
                        fallback_params["reasoning"] = {"effort": "low"}
                        fallback_params["text"] = {"verbosity": "medium"}

                    fallback_resp = client.responses.create(**fallback_params)

                    content = ""
                    if getattr(fallback_resp, 'output', None):
                        for item in fallback_resp.output:
                            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                                for c in item.content:
                                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                                        content = c.text
                                        break
                            if content:
                                break

                    if not content and hasattr(fallback_resp, 'output_text'):
                        content = fallback_resp.output_text

                    full_text = content
                    if full_text:
                        yield await send_regulatory_snapshot_chunk(full_text)

                except Exception as final_ex:
                    step2.error(f"Regulatory snapshot generation failed: {str(final_ex)}")
                    yield await send_reasoning_step(step2.to_dict())
                    yield await send_error(f"Failed to generate regulatory snapshot: {str(final_ex)}")
                    return

            # Step 3: Complete and Send Results
            step2.complete()
            step2.content = "Regulatory snapshot generated successfully."
            step2.details = full_text
            yield await send_reasoning_step(step2.to_dict())

            # Send completion with full text
            completion_data = {
                "institution_name": institution_name,
                "regulatory_snapshot": full_text,
                "generated_at": datetime.utcnow().isoformat(),
                "ai_model": exam_model
            }
            yield await send_completion(completion_data)

        except Exception as e:
            yield await send_error(f"Unexpected error generating regulatory snapshot: {str(e)}")

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
