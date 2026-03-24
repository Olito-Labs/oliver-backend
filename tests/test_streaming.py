"""Tests for SSE streaming format and streaming endpoint behavior."""
import pytest
import json
from unittest.mock import MagicMock

from app.api.streaming import (
    send_reasoning_step,
    send_progress_update,
    send_completion,
    send_error,
    send_letter_chunk,
    send_tool_call,
    send_tool_result,
    ReasoningStep,
)


class TestSSEFormatHelpers:
    """Verify SSE helpers produce correct 'data: ...\n\n' format."""

    @pytest.mark.asyncio
    async def test_reasoning_step_format(self):
        step = ReasoningStep("Test", "content", "brain")
        result = await send_reasoning_step(step)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "reasoning_step"
        assert payload["data"]["title"] == "Test"
        assert payload["data"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_progress_update_format(self):
        result = await send_progress_update(3, 10, "Processing")
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "progress"
        assert payload["data"]["current"] == 3
        assert payload["data"]["total"] == 10

    @pytest.mark.asyncio
    async def test_completion_format(self):
        result = await send_completion({"key": "value"})
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "completion"
        assert payload["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_error_format(self):
        result = await send_error("something broke")
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "error"
        assert payload["data"]["message"] == "something broke"

    @pytest.mark.asyncio
    async def test_letter_chunk_format(self):
        result = await send_letter_chunk("Hello world")
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "letter_chunk"
        assert payload["data"]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_tool_call_format(self):
        result = await send_tool_call("my_tool", {"arg": 1})
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "tool_call"
        assert payload["data"]["tool"] == "my_tool"

    @pytest.mark.asyncio
    async def test_tool_result_format(self):
        result = await send_tool_result("my_tool", {"ok": True})
        payload = json.loads(result[len("data: "):-2])
        assert payload["type"] == "tool_result"
        assert payload["data"]["result"]["ok"] is True


class TestReasoningStep:
    """ReasoningStep state transitions."""

    def test_complete_sets_status(self):
        step = ReasoningStep("T", "C", "brain")
        assert step.status == "active"
        step.complete()
        assert step.status == "completed"

    def test_error_sets_status_and_message(self):
        step = ReasoningStep("T", "C", "brain")
        step.error("fail")
        assert step.status == "error"
        assert step.content == "fail"

    def test_to_dict_contains_all_fields(self):
        step = ReasoningStep("T", "C", "brain", details="d")
        d = step.to_dict()
        assert set(d.keys()) == {"id", "title", "content", "status", "timestamp", "icon", "details"}


class TestStreamingEndpoints:
    """Integration tests for streaming endpoints."""

    def test_fdl_ingest_requires_params(self, client):
        """Missing document_id or study_id should return 400."""
        resp = client.post("/api/streaming/fdl/ingest", json={})
        assert resp.status_code == 400

    def test_fdl_ingest_text_requires_params(self, client):
        """Missing text or study_id should return 400."""
        resp = client.post("/api/streaming/fdl/ingest-text", json={"study_id": "s1"})
        assert resp.status_code == 400

        resp2 = client.post("/api/streaming/fdl/ingest-text", json={"text": "hello"})
        assert resp2.status_code == 400

    def test_fdl_ingest_streams_connected_event(self, client, mock_supabase):
        """Valid request should stream events starting with 'connected'."""
        doc = {
            "id": "d1", "filename": "fdl.pdf", "file_size": 100,
            "file_type": "application/pdf", "file_path": "u/s/f.pdf",
            "extracted_text": "Sample FDL text with requests",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        result = MagicMock()
        result.data = doc
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = result

        resp = client.post(
            "/api/streaming/fdl/ingest",
            json={"document_id": "d1", "study_id": "s1"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse first SSE line
        lines = resp.text.strip().split("\n\n")
        assert len(lines) >= 1
        first = lines[0]
        assert first.startswith("data: ")
        payload = json.loads(first[len("data: "):])
        assert payload["type"] == "connected"

    def test_simulate_fdl_streams_events(self, client, mock_openai):
        """Simulate FDL endpoint should return streaming response."""
        # Set up the mock to return a response with output
        mock_client = mock_openai.get_client.return_value
        mock_stream_ctx = MagicMock()
        mock_event = MagicMock()
        mock_event.type = "response.output_text.delta"
        mock_event.delta = "Dear Bank,"
        mock_stream_ctx.__enter__ = MagicMock(return_value=iter([mock_event]))
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)
        mock_client.responses.stream.return_value = mock_stream_ctx

        resp = client.post(
            "/api/streaming/fdl/simulate",
            json={"regulator": "OCC", "organization": "Test Bank"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
