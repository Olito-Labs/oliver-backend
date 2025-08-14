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
from app.config import settings

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
        "Given source documents (e.g., first-day letters, scoping memos), produce a concise json with: "
        "checklist: [ {id, title, description, category, due_date?, priority, owner?} ], "
        "requests: [ {id, request_code?, description, due_date?, owner?} ], "
        "summary: short text, total_items, critical_dates[]. Respond in valid json only."
    )
    user_prompt = (
        "Analyze the following document for examination prep and extract checklist and requests as json.\n\n"
        f"{document_text}\n\nRespond in valid json."
    )

    # Build parameters based on model type
    request_params = {
        "model": settings.OPENAI_MODEL,
        "input": user_prompt,
        "instructions": system_prompt,
        "max_output_tokens": 6000,
        "text": {"format": {"type": "json_object"}},
        "store": True,
        "stream": False,
    }
    
    # Add model-specific parameters
    if settings.OPENAI_MODEL.startswith("gpt-5"):
        request_params["reasoning"] = {"effort": "medium"}  # Thorough analysis for documents
        request_params["text"]["verbosity"] = "high"  # Detailed extraction results
    elif settings.OPENAI_MODEL.startswith("o3"):
        request_params["reasoning"] = {"effort": "medium", "summary": "detailed"}
    else:
        request_params["temperature"] = 0.7  # Consistent extraction for other models
    
    response = client.responses.create(**request_params)

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
        except Exception as url_ex:
            print(f"[exam] URL error: {url_ex}")
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

    except HTTPException as he:
        print(f"[exam] HTTPException during upload: {he}")
        raise
    except Exception as e:
        # Best-effort cleanup
        try:
            supabase.storage.from_('exam-documents').remove([file_path])
        except Exception:
            pass
        print(f"[exam] Upload failed: {e}")
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


# ============================
# Requests & FDL Ingestion
# ============================

class ExamRequest(BaseModel):
    id: Optional[str] = None
    study_id: str
    user_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    status: Optional[str] = 'not_started'
    source: Optional[str] = 'ad_hoc'
    request_code: Optional[str] = None
    priority: Optional[int] = 0
    regulatory_deadline: Optional[datetime] = None
    internal_due_date: Optional[datetime] = None
    owner: Optional[str] = None
    reviewer: Optional[str] = None


@router.get("/requests/study/{study_id}")
async def list_requests(study_id: str, user=Depends(get_current_user)):
    result = supabase.table('exam_requests').select("*") \
        .eq('study_id', study_id).eq('user_id', user['uid']) \
        .order('internal_due_date', desc=True).execute()
    return {"requests": result.data or []}


@router.post("/requests")
async def create_request(payload: Dict[str, Any], user=Depends(get_current_user)):
    payload['user_id'] = user['uid']
    result = supabase.table('exam_requests').insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create request")
    return {"request": result.data[0]}


@router.patch("/requests/{request_id}")
async def update_request(request_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    result = supabase.table('exam_requests').update(payload) \
        .eq('id', request_id).eq('user_id', user['uid']).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request": result.data[0]}


@router.delete("/requests/{request_id}")
async def delete_request(request_id: str, user=Depends(get_current_user)):
    # Ensure ownership via filter
    result = supabase.table('exam_requests').delete() \
        .eq('id', request_id).eq('user_id', user['uid']).execute()
    if result.data is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"message": "Request deleted"}


@router.post("/requests/{request_id}/documents")
async def link_document_to_request(request_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    document_id = payload.get('document_id')
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id is required")

    # Verify request ownership
    req = supabase.table('exam_requests').select('id') \
        .eq('id', request_id).eq('user_id', user['uid']).single().execute()
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")

    # Verify document ownership
    doc = supabase.table('exam_documents').select('id') \
        .eq('id', document_id).eq('user_id', user['uid']).single().execute()
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    result = supabase.table('exam_request_documents').insert({
        'request_id': request_id,
        'document_id': document_id
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to link document")
    return {"link": result.data[0]}


@router.get("/requests/{request_id}/documents")
async def list_request_documents(request_id: str, user=Depends(get_current_user)):
    # Ownership via join
    sql = (
        "select d.* from exam_request_documents rd "
        "join exam_requests r on r.id = rd.request_id "
        "join exam_documents d on d.id = rd.document_id "
        "where rd.request_id = :rid and r.user_id = :uid"
    )
    # Supabase Python client lacks bind parameters for RPC-free raw SQL; use two-step listing
    # 1) list links for this request (RLS ensures user)
    links = supabase.table('exam_request_documents').select('*').eq('request_id', request_id).execute()
    doc_ids = [l['document_id'] for l in (links.data or [])]
    if not doc_ids:
        return {"documents": []}
    docs = supabase.table('exam_documents').select('*').in_('id', doc_ids).execute()
    return {"documents": docs.data or []}


@router.post("/requests/{request_id}/validate")
async def validate_request(request_id: str, user=Depends(get_current_user)):
    # Get request
    req = supabase.table('exam_requests').select('*').eq('id', request_id).eq('user_id', user['uid']).single().execute()
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")

    # Get linked documents
    links = supabase.table('exam_request_documents').select('*').eq('request_id', request_id).execute()
    doc_ids = [l['document_id'] for l in (links.data or [])]
    docs = []
    if doc_ids:
        docs_result = supabase.table('exam_documents').select('*').in_('id', doc_ids).execute()
        docs = docs_result.data or []

    # Build context text (filenames + any analysis summaries)
    context_items = []
    for d in docs:
        ctx = f"Document: {d.get('filename','')}\n"
        if d.get('analysis_results'):
            ctx += f"Prior analysis summary: {str(d['analysis_results'])[:800]}\n"
        context_items.append(ctx)
    context_text = "\n\n".join(context_items) or "No linked evidence yet."

    client = openai_manager.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="OpenAI client not available")

    system_prompt = (
        "You are Oliver, validating examination evidence against a specific request. "
        "Return JSON with: gaps:[{issue,why_it_matters,missing_elements}], "
        "sufficiency:'insufficient|partial|sufficient', suggestions:[string], draft_narrative:string."
    )
    user_prompt = (
        f"Request:\n{req.data.get('title','')}\n{req.data.get('description','')}\n\n"
        f"Linked Evidence Context:\n{context_text}"
    )

    # Build parameters based on model type for validation
    request_params = {
        "model": settings.OPENAI_MODEL,
        "input": user_prompt,
        "instructions": system_prompt,
        "max_output_tokens": 6000,
        "text": {"format": {"type": "json_object"}},
        "store": True,
        "stream": False,
    }
    
    # Add model-specific parameters
    if settings.OPENAI_MODEL.startswith("gpt-5"):
        request_params["reasoning"] = {"effort": "medium"}  # Careful validation analysis
        request_params["text"]["verbosity"] = "medium"  # Balanced validation detail
    elif settings.OPENAI_MODEL.startswith("o3"):
        request_params["reasoning"] = {"effort": "medium", "summary": "detailed"}
    else:
        request_params["temperature"] = 0.7  # Consistent validation for other models
    
    response = client.responses.create(**request_params)

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
        raise HTTPException(status_code=500, detail="No response content from OpenAI")

    import json as _json
    try:
        data = _json.loads(content)
    except Exception:
        data = {"sufficiency": "partial", "gaps": [], "suggestions": [content[:800]], "draft_narrative": ""}

    return {"validation": data}


@router.post("/fdl/ingest")
async def ingest_first_day_letter(payload: Dict[str, Any], user=Depends(get_current_user)):
    document_id = payload.get('document_id')
    study_id = payload.get('study_id')
    if not document_id or not study_id:
        raise HTTPException(status_code=400, detail="document_id and study_id are required")

    # Load document
    doc_result = supabase.table('exam_documents').select('*').eq('id', document_id).eq('user_id', user['uid']).single().execute()
    if not doc_result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    document = doc_result.data

    # Download and extract text
    file_bytes = supabase.storage.from_('exam-documents').download(document['file_path'])
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(document['filename'])[1]) as tmpf:
        tmpf.write(file_bytes)
        tmp_path = tmpf.name
    try:
        text = _extract_text(tmp_path, document['file_type'])
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Analyze to extract requests
    client = openai_manager.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="OpenAI client not available")

    system_prompt = (
        "Extract distinct information requests (RFI) from the First Day Letter. "
        "For each, return json fields: title, description, category, "
        "request_code if present, regulatory_deadline if present (ISO), priority (0-3). "
        "For category, use ONLY these exact values: "
        "'Credit Risk', 'Interest Rate Risk', 'Liquidity Risk', 'Price Risk', "
        "'Operational Risk', 'Compliance Risk', 'Strategic Risk', "
        "'Governance/Management Oversight', 'IT/Cybersecurity', 'BSA/AML', "
        "'Capital Adequacy/Financial Reporting', 'Asset Management/Trust'. "
        "If unsure, use 'Operational Risk'. Respond in valid json only."
    )
    # Ensure the input contains the word 'json' to satisfy Responses API when using text.format json_object
    user_prompt = (text[:200000] or "") + "\n\nReturn the result as valid json."

    # Build parameters based on model type for FDL ingestion
    request_params = {
        "model": settings.OPENAI_MODEL,
        "input": user_prompt,
        "instructions": system_prompt,
        "max_output_tokens": 8000,
        "text": {"format": {"type": "json_object"}},
        "store": True,
        "stream": False,
    }
    
    # Add model-specific parameters
    if settings.OPENAI_MODEL.startswith("gpt-5"):
        request_params["reasoning"] = {"effort": "medium"}  # Thorough FDL analysis
        request_params["text"]["verbosity"] = "high"  # Detailed request extraction
    elif settings.OPENAI_MODEL.startswith("o3"):
        request_params["reasoning"] = {"effort": "medium", "summary": "detailed"}
    else:
        request_params["temperature"] = 0.7  # Consistent extraction for other models
    
    resp = client.responses.create(**request_params)

    content = ""
    if resp.output:
        for item in resp.output:
            if getattr(item, 'type', '') == 'message' and getattr(item, 'content', None):
                for c in item.content:
                    if getattr(c, 'type', '') == 'output_text' and getattr(c, 'text', None):
                        content = c.text
                        break
            if content:
                break
    if not content and hasattr(resp, 'output_text'):
        content = resp.output_text
    if not content:
        raise HTTPException(status_code=500, detail="No extraction from OpenAI")

    import json as _json
    try:
        parsed = _json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse extraction JSON: {str(e)}")

    # Normalize to list
    rfis = parsed.get('requests') if isinstance(parsed, dict) else parsed
    if not isinstance(rfis, list):
        rfis = []

    # Valid enum values from database
    VALID_CATEGORIES = {
        'Credit Risk', 'Interest Rate Risk', 'Liquidity Risk', 'Price Risk',
        'Operational Risk', 'Compliance Risk', 'Strategic Risk',
        'Governance/Management Oversight', 'IT/Cybersecurity', 'BSA/AML',
        'Capital Adequacy/Financial Reporting', 'Asset Management/Trust'
    }
    
    # Category mapping for common variations
    CATEGORY_MAPPING = {
        'Corporate Governance': 'Governance/Management Oversight',
        'Governance': 'Governance/Management Oversight',
        'Management': 'Governance/Management Oversight',
        'Technology Risk': 'IT/Cybersecurity',
        'Cyber Risk': 'IT/Cybersecurity',
        'Technology': 'IT/Cybersecurity',
        'Market Risk': 'Price Risk',
        'Legal Risk': 'Compliance Risk',
        'Reputation Risk': 'Operational Risk',
        'Reputational Risk': 'Operational Risk',
        'Model Risk': 'Operational Risk'
    }
    
    def normalize_category(category: str) -> str:
        """Normalize category to valid enum value."""
        if not category:
            return 'Operational Risk'
        
        # Check if already valid
        if category in VALID_CATEGORIES:
            return category
            
        # Check mapping
        if category in CATEGORY_MAPPING:
            return CATEGORY_MAPPING[category]
            
        # Fallback
        return 'Operational Risk'

    # Insert rows
    rows = []
    for r in rfis:
        row = {
            'user_id': user['uid'],
            'study_id': study_id,
            'title': r.get('title') or (r.get('description') or '')[:120] or 'Request',
            'description': r.get('description') or '',
            'category': normalize_category(r.get('category')),
            'status': 'not_started',
            'source': 'fdl',
            'request_code': r.get('request_code'),
            'priority': r.get('priority') if isinstance(r.get('priority'), int) else 0,
            'regulatory_deadline': r.get('regulatory_deadline'),
            'internal_due_date': None,
            'owner': None,
            'reviewer': None
        }
        rows.append(row)

    inserted = []
    if rows:
        res = supabase.table('exam_requests').insert(rows).execute()
        inserted = res.data or []

    return {"created": len(inserted), "requests": inserted}


# ============================
# Exam Studies (isolated lane)
# ============================

@router.post("/studies/")
async def create_exam_study(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Create a dedicated Examination Prep study in exam_studies."""
    title = payload.get('title') or 'Examination Prep'
    study_row = {
        'user_id': user['uid'],
        'title': title,
        'description': payload.get('description'),
        'workflow_type': 'examination-prep',
        'status': 'active',
        'current_step': payload.get('current_step', 0),
        'workflow_status': payload.get('workflow_status', 'not_started'),
        'workflow_data': payload.get('workflow_data') or {}
    }
    res = supabase.table('exam_studies').insert(study_row).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create exam study")
    return {"study": res.data[0]}


@router.get("/studies/")
async def list_exam_studies(user=Depends(get_current_user)):
    res = supabase.table('exam_studies').select('*').eq('user_id', user['uid']).order('last_message_at', desc=True).limit(100).execute()
    return {"studies": res.data or []}


@router.get("/studies/{study_id}")
async def get_exam_study(study_id: str, user=Depends(get_current_user)):
    res = supabase.table('exam_studies').select('*').eq('id', study_id).eq('user_id', user['uid']).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Study not found")
    return {"study": res.data}


@router.patch("/studies/{study_id}")
async def update_exam_study(study_id: str, payload: Dict[str, Any], user=Depends(get_current_user)):
    allowed = {k: v for k, v in payload.items() if k in ['title','description','current_step','workflow_status','workflow_data']}
    if not allowed:
        return {"study": (supabase.table('exam_studies').select('*').eq('id', study_id).eq('user_id', user['uid']).single().execute().data)}
    res = supabase.table('exam_studies').update(allowed).eq('id', study_id).eq('user_id', user['uid']).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Study not found")
    return {"study": res.data[0]}

