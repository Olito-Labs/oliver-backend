from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import os
from datetime import datetime

from app.supabase_client import supabase
from app.auth import get_current_user

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Request/Response models
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: str
    upload_url: str
    study_id: str
    user_id: str
    created_at: str
    processing_status: str

class DocumentAnalysisRequest(BaseModel):
    document_id: str
    analysis_type: str = "mra-intake"

@router.post("/upload", response_model=Dict[str, DocumentResponse])
async def upload_document(
    file: UploadFile = File(...),
    study_id: str = Form(...),
    user=Depends(get_current_user)
):
    """Upload a document to Supabase Storage and create a database record"""
    try:
        # Validate file type
        allowed_types = ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file.content_type} not supported. Please upload PDF, DOC, or DOCX files."
            )
        
        # Validate file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 50MB limit"
            )
        
        # Reset file pointer
        await file.seek(0)
        
        # Generate unique file path: user_id/study_id/filename
        file_extension = os.path.splitext(file.filename)[1] if file.filename else '.pdf'
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = f"{user['uid']}/{study_id}/{unique_filename}"
        
        # Upload to Supabase Storage
        upload_result = supabase.storage.from_('mra-documents').upload(
            file_path, 
            file_content,
            {
                'content-type': file.content_type,
                'x-upsert': 'true'  # Allow overwrite if needed
            }
        )
        
        if upload_result.error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {upload_result.error.message}"
            )
        
        # Get public URL for the uploaded file
        url_result = supabase.storage.from_('mra-documents').get_public_url(file_path)
        
        # Create document record in database
        document_data = {
            'id': str(uuid.uuid4()),
            'filename': file.filename or 'uploaded_document.pdf',
            'file_size': len(file_content),
            'file_type': file.content_type,
            'file_path': file_path,
            'upload_url': url_result['publicURL'] if 'publicURL' in url_result else '',
            'study_id': study_id,
            'user_id': user['uid'],
            'processing_status': 'uploaded'
        }
        
        # Insert into documents table
        result = supabase.table('documents').insert(document_data).execute()
        
        if not result.data:
            # Cleanup: delete uploaded file if database insert failed
            supabase.storage.from_('mra-documents').remove([file_path])
            raise HTTPException(status_code=500, detail="Failed to create document record")
        
        document = result.data[0]
        
        return {"document": document}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

@router.get("/{document_id}", response_model=Dict[str, DocumentResponse])
async def get_document(document_id: str, user=Depends(get_current_user)):
    """Get a specific document"""
    try:
        result = supabase.table('documents')\
            .select("*")\
            .eq('id', document_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"document": result.data}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(status_code=500, detail=f"Error fetching document: {str(e)}")

@router.get("/study/{study_id}", response_model=Dict[str, List[DocumentResponse]])
async def get_study_documents(study_id: str, user=Depends(get_current_user)):
    """Get all documents for a study"""
    try:
        result = supabase.table('documents')\
            .select("*")\
            .eq('study_id', study_id)\
            .eq('user_id', user['uid'])\
            .order('created_at', desc=True)\
            .execute()
        
        return {"documents": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching study documents: {str(e)}")

@router.delete("/{document_id}")
async def delete_document(document_id: str, user=Depends(get_current_user)):
    """Delete a document and its file from storage"""
    try:
        # Get document info first
        result = supabase.table('documents')\
            .select("*")\
            .eq('id', document_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = result.data
        
        # Delete from storage
        if document.get('file_path'):
            supabase.storage.from_('mra-documents').remove([document['file_path']])
        
        # Delete from database
        supabase.table('documents')\
            .delete()\
            .eq('id', document_id)\
            .eq('user_id', user['uid'])\
            .execute()
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@router.post("/{document_id}/analyze")
async def analyze_document(
    document_id: str, 
    request: DocumentAnalysisRequest,
    user=Depends(get_current_user)
):
    """Trigger AI analysis of an uploaded document"""
    try:
        # Get document info
        doc_result = supabase.table('documents')\
            .select("*")\
            .eq('id', document_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_result.data
        
        # Update processing status
        supabase.table('documents')\
            .update({'processing_status': 'analyzing'})\
            .eq('id', document_id)\
            .execute()
        
        # TODO: Implement actual document analysis with OpenAI
        # For now, return a placeholder response
        
        return {
            "message": "Document analysis started",
            "document_id": document_id,
            "analysis_type": request.analysis_type,
            "status": "analyzing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing document: {str(e)}")