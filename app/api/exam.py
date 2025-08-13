from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import os
import tempfile
from datetime import datetime

from app.supabase_client import supabase
from app.auth import get_current_user
from app.llm_providers import openai_manager

# Optional PDF/DOCX parsing
import fitz  # PyMuPDF
try:
    import docx
except ImportError:
    docx = None

router = APIRouter(prefix="/api/exam", tags=["examination"])


class ExamDocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: str
    upload_url: str
    study_id: str
    user_id: str
    created_at: Optional[str] = None
    processing_status: Optional[str] = None
    analysis_results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


def _extract_text_from_pdf(file_path: str) -> str:
    try:
        doc = fitz.open(file_path)
        text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            text += f"--- Page {page_num + 1} ---\n" + page_text + "\n\n"
        doc.close()
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def _extract_text_from_docx(file_path: str) -> str:
    if docx is None:
        raise Exception("python-docx library not available")
    try:
        d = docx.Document(file_path)
        text = "\n".join([p.text for p in d.paragraphs])
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to extract text from DOCX: {str(e)}")


def _extract_text(file_path: str, file_type: str) -> str:
    file_type = file_type.lower()
    if file_type == 'application/pdf':
        return _extract_text_from_pdf(file_path)
    if file_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
        return _extract_text_from_docx(file_path)
    raise Exception(f"Unsupported file type: {file_type}")


async def _analyze_exam_document_with_o3(document_text: str) -> Dict[str, Any]:
    """Minimal structured analysis for examination prep (first-day letter/checklist synthesis)."""
    client = openai_manager.get_client()
    if not client:
        raise Exception("OpenAI client not available")

    system_prompt = (
        "You are Oliver, assisting with bank regulatory examination preparation. "
        "Given source documents (e.g., first-day letters, scoping memos), produce a concise JSON with: "
        "checklist: [ {id, title, description, category, due_date?, priority, owner?} ], "
        "requests: [ {id, request_code?, description, due_date?, owner?} ], "
        "summary: short text, total_items, critical_dates[]. Return valid JSON only."
    )
    user_prompt = f"Analyze the following document for examination prep and extract checklist and requests as JSON.\n\n{document_text}"

    response = client.responses.create(
        model="o3",
        input=user_prompt,
        instructions=system_prompt,
        max_output_tokens=6000,
        text={"format": {"type": "json_object"}},
        reasoning={"effort": "medium", "summary": "detailed"},
        store=True,
        stream=False,
    )

    content = ""
    if response.output:
        for item in response.output:
            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                for c in item.content:
                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                        content = c.text
                        break
            if content:
                break
    if not content and hasattr(response, 'output_text'):
        content = response.output_text
    if not content:
        raise Exception("No response content received from OpenAI")

    import json as _json
    return _json.loads(content)


@router.post("/documents/upload", response_model=Dict[str, ExamDocumentResponse])
async def upload_exam_document(
    file: UploadFile = File(...),
    study_id: str = Form(...),
    user=Depends(get_current_user)
):
    try:
        allowed_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

        ext = os.path.splitext(file.filename)[1] if file.filename else '.pdf'
        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{user['uid']}/{study_id}/{unique_name}"

        # Upload to exam bucket
        upload_result = supabase.storage.from_('exam-documents').upload(
            file_path, content, {'content-type': file.content_type, 'x-upsert': 'true'}
        )
        print(f"[exam] Upload result: {upload_result}")

        # Public URL
        try:
            url_result = supabase.storage.from_('exam-documents').get_public_url(file_path)
        except Exception:
            url_result = {'publicURL': ''}
        upload_url = ''
        if hasattr(url_result, 'publicURL'):
            upload_url = url_result.publicURL
        elif isinstance(url_result, dict):
            upload_url = url_result.get('publicURL', '')
        elif isinstance(url_result, str):
            upload_url = url_result

        row = {
            'id': str(uuid.uuid4()),
            'filename': file.filename or 'uploaded_document.pdf',
            'file_size': len(content),
            'file_type': file.content_type,
            'file_path': file_path,
            'upload_url': upload_url,
            'study_id': study_id,
            'user_id': user['uid'],
            'processing_status': 'uploaded',
        }

        result = supabase.table('exam_documents').insert(row).execute()
        if not result.data:
            raise Exception("No data returned from database insert")
        return {"document": result.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        # Best-effort cleanup
        try:
            supabase.storage.from_('exam-documents').remove([file_path])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to create exam document record: {str(e)}")


@router.get("/documents/{document_id}", response_model=Dict[str, ExamDocumentResponse])
async def get_exam_document(document_id: str, user=Depends(get_current_user)):
    result = supabase.table('exam_documents').select("*").eq('id', document_id).eq('user_id', user['uid']).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": result.data}


@router.get("/documents/study/{study_id}", response_model=Dict[str, List[ExamDocumentResponse]])
async def list_exam_documents(study_id: str, user=Depends(get_current_user)):
    result = supabase.table('exam_documents').select("*").eq('study_id', study_id).eq('user_id', user['uid']).order('created_at', desc=True).execute()
    return {"documents": result.data or []}


@router.delete("/documents/{document_id}")
async def delete_exam_document(document_id: str, user=Depends(get_current_user)):
    result = supabase.table('exam_documents').select("*").eq('id', document_id).eq('user_id', user['uid']).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = result.data
    if doc.get('file_path'):
        supabase.storage.from_('exam-documents').remove([doc['file_path']])
    supabase.table('exam_documents').delete().eq('id', document_id).eq('user_id', user['uid']).execute()
    return {"message": "Document deleted"}


@router.post("/documents/{document_id}/analyze")
async def analyze_exam_document(document_id: str, user=Depends(get_current_user)):
    try:
        doc_result = supabase.table('exam_documents').select("*").eq('id', document_id).eq('user_id', user['uid']).single().execute()
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        document = doc_result.data

        supabase.table('exam_documents').update({'processing_status': 'analyzing'}).eq('id', document_id).execute()

        # Download from storage
        file_bytes = supabase.storage.from_('exam-documents').download(document['file_path'])
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(document['filename'])[1]) as tmpf:
            tmpf.write(file_bytes)
            tmp_path = tmpf.name
        try:
            text = _extract_text(tmp_path, document['file_type'])
            if not text.strip():
                raise Exception("No text could be extracted from the document")
            analysis = await _analyze_exam_document_with_o3(text)
            supabase.table('exam_documents').update({'processing_status': 'completed', 'analysis_results': analysis}).eq('id', document_id).execute()
            return {"message": "Analysis completed", "document_id": document_id, "results": analysis}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        supabase.table('exam_documents').update({'processing_status': 'failed', 'error_message': str(e)}).eq('id', document_id).execute()
        raise HTTPException(status_code=500, detail=f"Error analyzing document: {str(e)}")


