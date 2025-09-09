from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, Any
import json
from datetime import datetime

from app.auth import get_current_user
from app.llm_providers import openai_manager
from app.config import settings
from app.supabase_client import supabase

router = APIRouter(prefix="/api/regulatory", tags=["regulatory"])


class RegulatorySnapshotRequest(BaseModel):
    institution: str


def _build_system_prompt() -> str:
    return (
        "You are Oliver, a banking regulatory assistant. Produce a succinct 3-sentence "
        "regulatory snapshot for the provided institution name. Keep it dignified and neutral.\n\n"
        "Guidelines:\n"
        "- If the specific institution's regulator is not known from the name alone, generalize based on typical US banking supervision (e.g., OCC/FDIC/Fed or state regulators).\n"
        "- Mention likely supervisory focus areas relevant to most banks (e.g., BSA/AML, credit risk, liquidity, operational/IT, governance).\n"
        "- Reference current macro/regulatory themes at a high level (e.g., interest rate risk management, Basel III endgame, operational resilience) without fabricating specifics.\n"
        "- Absolutely no invented facts or numbers about the institution.\n"
        "- Exactly 3 sentences."
    )


def _build_user_prompt(institution: str) -> str:
    return (
        f"Institution: {institution}\n\n"
        "Create a succinct, dignified 3-sentence regulatory snapshot suitable for an executive dashboard."
    )


async def _stream_snapshot(client, params: Dict[str, Any], user_id: str, institution: str) -> AsyncGenerator[str, None]:
    try:
        stream = client.responses.create(stream=True, **params)
        accumulated = ""

        # Send initial event
        start_evt = {
            "type": "start",
            "metadata": {
                "model": params.get("model"),
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
        yield f"data: {json.dumps(start_evt)}\n\n"

        for event in stream:
            et = getattr(event, "type", None)

            if et == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    accumulated += delta
                    yield f"data: {json.dumps({'type': 'content', 'content': delta, 'done': False})}\n\n"
            elif et and ("output" in et or "text" in et) and "delta" in et and "reasoning" not in et:
                delta = getattr(event, "delta", "")
                if delta:
                    accumulated += delta
                    yield f"data: {json.dumps({'type': 'content', 'content': delta, 'done': False})}\n\n"
            elif et in ("response.error", "response.failed"):
                msg = getattr(event, "error", "Unknown error")
                yield f"data: {json.dumps({'type': 'error', 'content': str(msg), 'done': True})}\n\n"
                return

        # Persist to Supabase (best-effort)
        ts = datetime.utcnow().isoformat()
        try:
            supabase.table('user_preferences').upsert(
                {
                    'user_id': user_id,
                    'institution_name': institution,
                    'regulatory_snapshot': accumulated,
                    'regulatory_snapshot_updated_at': ts
                },
                on_conflict='user_id'
            ).execute()
        except Exception as e:
            # Log for troubleshooting but keep streaming resilient
            print(f"[regulatory] Upsert failed: {e}")
            # Non-fatal; continue
            pass

        # Completion event (include timestamp)
        completion = {
            "type": "done",
            "content": accumulated,
            "updated_at": ts,
            "done": True,
        }
        yield f"data: {json.dumps(completion)}\n\n"

    except Exception as e:
        err = {"type": "error", "content": f"Error: {str(e)}", "done": True}
        yield f"data: {json.dumps(err)}\n\n"


@router.post("/snapshot")
async def generate_regulatory_snapshot(payload: RegulatorySnapshotRequest, user=Depends(get_current_user)):
    try:
        institution = (payload.institution or "").strip()
        if not institution:
            raise HTTPException(status_code=400, detail="institution is required")

        client = openai_manager.get_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI client not available")

        model = settings.OPENAI_EXAM_MODEL or settings.OPENAI_MODEL
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(institution)

        request_params: Dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                    ],
                }
            ],
            "instructions": system_prompt,
            "max_output_tokens": 600,
            "store": False,
        }

        # GPT-5 specific knobs
        if str(model).startswith("gpt-5"):
            request_params["reasoning"] = {"effort": "low"}
            request_params["text"] = {"verbosity": "medium"}

        return StreamingResponse(
            _stream_snapshot(client, request_params, user['uid'], institution),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regulatory snapshot failed: {str(e)}")


