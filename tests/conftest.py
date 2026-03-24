import sys
import pytest
from unittest.mock import MagicMock, patch


# We must mock supabase.create_client BEFORE any app module is imported,
# because app.supabase_client calls create_client() at module level.
_mock_supabase_instance = MagicMock()


def _fake_create_client(*args, **kwargs):
    return _mock_supabase_instance


# Patch before any app.* import
patch("supabase.create_client", _fake_create_client).start()

# Also need to set env vars so Settings doesn't fail and OpenAI doesn't init
import os
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Now we can safely import app modules
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _reset_mock_supabase():
    """Reset the shared supabase mock with sensible defaults."""
    _mock_supabase_instance.reset_mock()
    result = MagicMock()
    result.data = []
    # Chain defaults
    _mock_supabase_instance.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = result
    _mock_supabase_instance.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = result
    _mock_supabase_instance.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = result
    _mock_supabase_instance.table.return_value.insert.return_value.execute.return_value = result
    _mock_supabase_instance.table.return_value.update.return_value.eq.return_value.execute.return_value = result
    _mock_supabase_instance.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = result
    _mock_supabase_instance.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = result
    # Storage
    _mock_supabase_instance.storage.from_.return_value.upload.return_value = MagicMock()
    _mock_supabase_instance.storage.from_.return_value.get_public_url.return_value = "https://example.com/file.pdf"
    _mock_supabase_instance.storage.from_.return_value.download.return_value = b"fake pdf bytes"
    _mock_supabase_instance.storage.from_.return_value.remove.return_value = MagicMock()


@pytest.fixture(autouse=True)
def mock_supabase():
    """Provide a fresh supabase mock for each test."""
    _reset_mock_supabase()
    # Patch the reference in each module that imported it
    with patch("app.supabase_client.supabase", _mock_supabase_instance), \
         patch("app.api.exam.supabase", _mock_supabase_instance), \
         patch("app.api.streaming.supabase", _mock_supabase_instance):
        yield _mock_supabase_instance


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI manager so no real API calls are made."""
    mock_manager = MagicMock()
    mock_client = MagicMock()
    mock_manager.get_client.return_value = mock_client
    mock_manager.initialize_client.return_value = None
    mock_manager.get_current_provider_info.return_value = {
        "provider": "openai", "model": "gpt-5-mini"
    }

    with patch("app.llm_providers.openai_manager", mock_manager), \
         patch("app.api.exam.openai_manager", mock_manager), \
         patch("app.api.streaming.openai_manager", mock_manager), \
         patch("app.main.openai_manager", mock_manager):
        yield mock_manager


@pytest.fixture()
def client():
    """TestClient for the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def demo_user():
    return {
        "uid": "550e8400-e29b-41d4-a716-446655440000",
        "email": "demo@example.com"
    }
