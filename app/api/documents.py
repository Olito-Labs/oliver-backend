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
        
        # Read file content once
        file_content = await file.read()
        print(f"File read: {file.filename}, size: {len(file_content)} bytes, type: {file.content_type}")
        
        # Validate file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 50MB limit"
            )
        
        # Generate unique file path: user_id/study_id/filename
        file_extension = os.path.splitext(file.filename)[1] if file.filename else '.pdf'
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = f"{user['uid']}/{study_id}/{unique_filename}"
        print(f"Upload path: {file_path}")
        
        # Upload to Supabase Storage
        try:
            upload_result = supabase.storage.from_('mra-documents').upload(
                file_path, 
                file_content,
                {
                    'content-type': file.content_type,
                    'x-upsert': 'true'  # Allow overwrite if needed
                }
            )
            print(f"Upload result: {upload_result}")
        except Exception as upload_error:
            print(f"Upload error: {upload_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {str(upload_error)}"
            )
        
        # Get public URL for the uploaded file
        try:
            url_result = supabase.storage.from_('mra-documents').get_public_url(file_path)
            print(f"URL result: {url_result}")
        except Exception as url_error:
            print(f"URL error: {url_error}")
            # Continue without public URL if this fails
            url_result = {'publicURL': ''}
        
        # Create document record in database
        # Handle different URL result formats
        upload_url = ''
        if hasattr(url_result, 'publicURL'):
            upload_url = url_result.publicURL
        elif isinstance(url_result, dict):
            upload_url = url_result.get('publicURL', '')
        elif isinstance(url_result, str):
            upload_url = url_result
        
        document_data = {
            'id': str(uuid.uuid4()),
            'filename': file.filename or 'uploaded_document.pdf',
            'file_size': len(file_content),
            'file_type': file.content_type,
            'file_path': file_path,
            'upload_url': upload_url,
            'study_id': study_id,
            'user_id': user['uid'],
            'processing_status': 'uploaded'
        }
        
        # Insert into documents table
        try:
            result = supabase.table('documents').insert(document_data).execute()
            print(f"Database insert result: {result}")
            
            if not result.data:
                raise Exception("No data returned from database insert")
            
            document = result.data[0]
            print(f"Document created successfully: {document['id']}")
            
            return {"document": document}
            
        except Exception as db_error:
            print(f"Database error: {db_error}")
            # Cleanup: delete uploaded file if database insert failed
            try:
                supabase.storage.from_('mra-documents').remove([file_path])
                print(f"Cleaned up uploaded file: {file_path}")
            except Exception as cleanup_error:
                print(f"Failed to cleanup file: {cleanup_error}")
            
            raise HTTPException(status_code=500, detail=f"Failed to create document record: {str(db_error)}")
        
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