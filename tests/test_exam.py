"""Tests for exam upload endpoint, validation, and error handling."""
import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO


class TestUploadEndpoint:
    """POST /api/exam/documents/upload"""

    def test_upload_rejects_invalid_file_type(self, client):
        """Uploading a .txt file should return 400."""
        resp = client.post(
            "/api/exam/documents/upload",
            data={"study_id": "study-1"},
            files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_upload_rejects_oversized_file(self, client, mock_supabase):
        """File over 50MB should return 400."""
        big_content = b"x" * (51 * 1024 * 1024)
        resp = client.post(
            "/api/exam/documents/upload",
            data={"study_id": "study-1"},
            files={"file": ("big.pdf", BytesIO(big_content), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "50MB" in resp.json()["detail"]

    def test_upload_success(self, client, mock_supabase):
        """Successful PDF upload returns document data."""
        doc_row = {
            "id": "doc-1",
            "filename": "test.pdf",
            "file_size": 100,
            "file_type": "application/pdf",
            "upload_url": "https://example.com/test.pdf",
            "study_id": "study-1",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "processing_status": "uploaded",
            "created_at": None,
            "analysis_results": None,
            "error_message": None,
        }

        ensure_select = MagicMock()
        ensure_select.data = None
        ensure_insert = MagicMock()
        ensure_insert.data = [{}]

        insert_result = MagicMock()
        insert_result.data = [doc_row]

        def table_dispatch(name):
            m = MagicMock()
            if name == "studies":
                m.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = ensure_select
                m.insert.return_value.execute.return_value = ensure_insert
            elif name == "exam_documents":
                m.insert.return_value.execute.return_value = insert_result
                update_result = MagicMock()
                update_result.data = [doc_row]
                m.update.return_value.eq.return_value.eq.return_value.execute.return_value = update_result
            return m

        mock_supabase.table.side_effect = table_dispatch

        with patch("app.api.exam._extract_text", return_value="Some extracted text"):
            resp = client.post(
                "/api/exam/documents/upload",
                data={"study_id": "study-1"},
                files={"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "document" in body
        assert body["document"]["id"] == "doc-1"


class TestGetDocument:
    """GET /api/exam/documents/{document_id}"""

    def test_get_document_not_found(self, client, mock_supabase):
        """When document not found, the select returns data=None -> 404."""
        result = MagicMock()
        result.data = None

        def table_dispatch(name):
            m = MagicMock()
            m.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = result
            return m

        mock_supabase.table.side_effect = table_dispatch
        resp = client.get("/api/exam/documents/nonexistent")
        assert resp.status_code == 404

    def test_get_document_found(self, client, mock_supabase):
        doc = {
            "id": "doc-1", "filename": "a.pdf", "file_size": 10,
            "file_type": "application/pdf", "upload_url": "",
            "study_id": "s1", "user_id": "u1",
            "created_at": None, "processing_status": "uploaded",
            "analysis_results": None, "error_message": None,
        }
        result = MagicMock()
        result.data = doc

        def table_dispatch(name):
            m = MagicMock()
            m.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = result
            return m

        mock_supabase.table.side_effect = table_dispatch
        resp = client.get("/api/exam/documents/doc-1")
        assert resp.status_code == 200
        assert resp.json()["document"]["id"] == "doc-1"


class TestListDocuments:
    """GET /api/exam/documents/study/{study_id}"""

    def test_list_returns_empty(self, client, mock_supabase):
        result = MagicMock()
        result.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = result

        resp = client.get("/api/exam/documents/study/s1")
        assert resp.status_code == 200
        assert resp.json()["documents"] == []


class TestDeleteDocument:
    """DELETE /api/exam/documents/{document_id}"""

    def test_delete_not_found(self, client, mock_supabase):
        """select returns data=None -> 404."""
        result = MagicMock()
        result.data = None

        def table_dispatch(name):
            m = MagicMock()
            m.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = result
            return m

        mock_supabase.table.side_effect = table_dispatch

        resp = client.delete("/api/exam/documents/nope")
        assert resp.status_code == 404

    def test_delete_success(self, client, mock_supabase):
        doc = {"id": "d1", "file_path": "u1/s1/file.pdf"}
        select_result = MagicMock()
        select_result.data = doc
        delete_result = MagicMock()
        delete_result.data = []

        call_count = [0]

        def table_dispatch(name):
            m = MagicMock()
            m.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = select_result
            m.delete.return_value.eq.return_value.eq.return_value.execute.return_value = delete_result
            return m

        mock_supabase.table.side_effect = table_dispatch

        resp = client.delete("/api/exam/documents/d1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Document deleted"


class TestTextExtraction:
    """Unit tests for _extract_text helpers."""

    def test_unsupported_type_raises(self):
        from app.api.exam import _extract_text
        with pytest.raises(Exception, match="Unsupported file type"):
            _extract_text("/tmp/fake", "image/png")
